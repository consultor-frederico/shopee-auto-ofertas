"""Mercado Livre (afiliado do Garimpo VIP), 04/11/2026. Ainda NÃO posta nada: só conecta e testa a busca.

Segredos (o Fred cadastra): ML_CLIENT_ID, ML_CLIENT_SECRET e ML_REFRESH_TOKEN (este sai do workflow 29).
Atenção: no Mercado Livre o refresh token só vale UMA vez. Toda troca devolve um novo, que o workflow
salva sozinho no segredo ML_REFRESH_TOKEN com o GH_PAT. Se uma rodada falhar antes de salvar, é só
conectar de novo pelo workflow 29.

Link de afiliado: o painel gera links cifrados (/social/<perfil>?...&ref=...), que não dá para gerar daqui.
O robô monta o endereço limpo do produto + a etiqueta (link_afiliado). Teste de 04/11: abre o produto;
falta confirmar se o clique conta no painel.

Uso:
  python -m src.mercadolivre conectar   → sem ML_CODIGO: imprime o link de autorização
                                          com ML_CODIGO: troca o código pelo refresh token
  python -m src.mercadolivre status     → confere o token e mostra a conta conectada
  python -m src.mercadolivre busca TERMO → testa a busca com token e mostra 5 resultados
                                          (sem ML_REFRESH_TOKEN tenta Client Credentials; se a busca
                                          recusar, imprime o link para conectar a conta)
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

API = "https://api.mercadolibre.com"
AUTH = "https://auth.mercadolivre.com.br/authorization"
REDIRECT = "https://garimpovipbr.github.io/"   # página pública sem o nome do Fred
ETIQUETA = os.getenv("ML_ETIQUETA", "garimpovip").strip() or "garimpovip"
MATT_TOOL = os.getenv("ML_MATT_TOOL", "42691474").strip() or "42691474"
ARQ_NOVO_TOKEN = Path(os.getenv("RUNNER_TEMP", "/tmp")) / "ml_refresh.txt"


def _env(nome):
    return os.getenv(nome, "").strip()


def ligado():
    return all(_env(n) for n in ("ML_CLIENT_ID", "ML_CLIENT_SECRET"))


def _token(dados):
    r = requests.post(f"{API}/oauth/token", timeout=30, data={
        "client_id": _env("ML_CLIENT_ID"), "client_secret": _env("ML_CLIENT_SECRET"), **dados},
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
    j = r.json() if r.content else {}
    if "access_token" not in j:
        raise RuntimeError(f"Mercado Livre recusou o token ({r.status_code}): {j.get('error')} {j.get('message')}")
    if j.get("refresh_token") and dados.get("grant_type") != "client_credentials":   # vale uma vez só: o workflow salva o novo no segredo
        ARQ_NOVO_TOKEN.write_text(j["refresh_token"])
    return j


_cache = {}


def access_token():
    """Com ML_REFRESH_TOKEN usa o token da conta; sem ele tenta Client Credentials (só ID + chave secreta)."""
    if "tok" not in _cache:
        if _env("ML_REFRESH_TOKEN"):
            dados = {"grant_type": "refresh_token", "refresh_token": _env("ML_REFRESH_TOKEN")}
        else:
            dados = {"grant_type": "client_credentials"}
        _cache["tok"] = _token(dados)["access_token"]
    return _cache["tok"]


def _get(caminho, **params):
    r = requests.get(f"{API}{caminho}", params=params, timeout=30,
                     headers={"Authorization": f"Bearer {access_token()}", "Accept": "application/json"})
    return r


def link_afiliado(url):
    """Endereço limpo do produto (/p/MLB... ou MLB-...) + etiqueta do Garimpo."""
    m = re.search(r"/p/(MLB\d+)", url)
    if m:
        base = f"https://www.mercadolivre.com.br/p/{m.group(1)}"
    else:
        p = urlparse(url)
        base = f"{p.scheme or 'https'}://{p.netloc}{p.path}"
    return f"{base}?matt_word={ETIQUETA}&matt_tool={MATT_TOOL}"


def _codigo():
    bruto = unquote(_env("ML_CODIGO"))
    if "code=" in bruto:   # o Fred pode colar o endereço inteiro da página
        bruto = parse_qs(urlparse(bruto).query).get("code", [bruto])[0]
    return bruto.strip()


def _conectar():
    if not _env("ML_CLIENT_ID"):
        sys.exit("Falta o segredo ML_CLIENT_ID.")
    codigo = _codigo()
    if not codigo:
        print("1) Abra este link no navegador logado na conta do Mercado Livre do afiliado e autorize:")
        print(f"{AUTH}?response_type=code&client_id={_env('ML_CLIENT_ID')}&redirect_uri={quote(REDIRECT, safe='')}")
        print("2) Vai abrir a página do Garimpo com ?code=TG-... no endereço. Copie o endereço inteiro e rode")
        print("   este workflow de novo colando no campo do código (vale ~10 min).")
        return
    j = _token({"grant_type": "authorization_code", "code": codigo, "redirect_uri": REDIRECT})
    print(f"✅ Conectado (escopos: {j.get('scope')}). O refresh token vai ser salvo no segredo ML_REFRESH_TOKEN.")


def _status():
    if not _env("ML_REFRESH_TOKEN"):
        access_token()
        print("✅ Entrou só com ID + chave secreta (Client Credentials).")
        return
    r = _get("/users/me")
    if r.status_code != 200:
        sys.exit(f"❌ /users/me respondeu {r.status_code}: {r.text[:300]}")
    u = r.json()
    print(f"✅ Token ok. Conta: {u.get('nickname')} (id {u.get('id')}).")


def _busca(termo):
    r = _get("/sites/MLB/search", q=termo, limit=5)
    if r.status_code != 200:
        print(f"❌ Busca respondeu {r.status_code}: {r.text[:300]}")
        if not _env("ML_REFRESH_TOKEN"):
            print("Próximo passo: conectar a conta. Abra o link abaixo, autorize e rode o 29 de novo colando o endereço.")
            _conectar()
        return
    itens = r.json().get("results", [])
    print(f"✅ Busca com token funcionou: {termo} · {len(itens)} resultados")
    for it in itens:
        print(f"• {it.get('title', '')[:70]} · R$ {it.get('price')} · vendidos: {it.get('sold_quantity', 'n/d')}"
              f" · {link_afiliado(it.get('permalink', ''))}")
    if itens:
        print("Campos:", ", ".join(sorted(itens[0].keys())))


def _sonda(termo):
    """Testa outros caminhos da API (a busca aberta /sites/MLB/search dá 403 até com token)."""
    def tenta(nome, caminho, **params):
        r = _get(caminho, **params)
        print(f"{'✅' if r.status_code == 200 else '❌'} {nome}: {r.status_code} · {r.text[:400]}")
        return r.json() if r.status_code == 200 else {}
    tenta("categoria do termo", "/sites/MLB/domain_discovery/search", q=termo, limit=1)
    cat = (tenta("categorias", "/sites/MLB/categories") or [{}])
    d = tenta("catálogo (products/search)", "/products/search", status="active", site_id="MLB", q=termo, limit=3)
    for res in (d.get("results") or [])[:1]:
        tenta("produto do catálogo", f"/products/{res.get('id')}")
        tenta("ofertas do produto", f"/products/{res.get('id')}/items", limit=3)
    h = tenta("mais vendidos (Casa, Móveis e Decoração)", "/highlights/MLB/category/MLB1574")
    for c in (h.get("content") or [])[:2]:
        tid = c.get("id")
        if c.get("type") == "PRODUCT":
            tenta("produto mais vendido", f"/products/{tid}")
            tenta("ofertas do mais vendido", f"/products/{tid}/items", limit=3)
        else:
            tenta("item mais vendido", f"/items/{tid}")
    tenta("item avulso", "/items", ids="MLB6756182602")


# Categorias do ranking de mais vendidos: id do ML → (nome, nicho do robô, comissão % do programa de afiliados)
# Comissões da tabela do programa (fonte de terceiros, 2025; conferir no painel quando sair a 1ª venda).
CATEGORIAS = {
    "MLB1574": ("Casa, Móveis e Decoração", "lar", 10.0),
    "MLB1246": ("Beleza e Cuidado Pessoal", "beleza", 16.0),
    "MLB1000": ("Eletrônicos, Áudio e Vídeo", "eletronicos", 9.5),
    "MLB1276": ("Esportes e Fitness", "masculino", 14.0),
    "MLB263532": ("Ferramentas", "lar", 10.0),
    "MLB5726": ("Eletrodomésticos", "lar", 10.0),
    "MLB1132": ("Brinquedos e Hobbies", "brinquedos", 10.0),
    "MLB1071": ("Animais", "pet", 9.0),
    "MLB5672": ("Acessórios para Veículos", "automotivo", 11.0),
    "MLB1648": ("Informática", "eletronicos", 9.5),
    "MLB1430": ("Calçados, Roupas e Bolsas", "moda", 14.0),
}

def _brl(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def produto(pid, categoria, posicao, nome_cat, pct=10.0):
    """Produto do catálogo → oferta no formato do robô (o mesmo da Shopee/AliExpress)."""
    r = _get(f"/products/{pid}")
    if r.status_code != 200:
        return None
    p = r.json()
    r2 = _get(f"/products/{pid}/items", limit=20)
    itens = r2.json().get("results", []) if r2.status_code == 200 else []
    itens = [i for i in itens if i.get("condition") == "new" and i.get("price")]
    if not itens:
        return None
    melhor = min(itens, key=lambda i: i["price"])
    preco = float(melhor["price"])
    de = melhor.get("original_price")
    desconto = round((1 - preco / de) * 100) if de and de > preco else 0
    fotos = [f.get("url") for f in p.get("pictures") or [] if f.get("url")]
    return {
        "id": f"ml{pid}",
        "nome": p.get("name", ""),
        "titulo": p.get("name", "")[:60],
        "categoria": categoria,
        "preco": preco,
        "preco_fmt": _brl(preco),
        "preco_de": de if desconto else None,
        "desconto": desconto,
        "comissao": round(preco * pct / 100, 2),
        "comissao_pct": pct,
        "vendas": 0,
        "nota": 0.0,
        "posicao": posicao,
        "info_txt": f"Top {posicao} mais vendidos em {nome_cat}",
        "loja": "Mercado Livre",
        "plataforma": "mercadolivre",
        "imagem": fotos[0] if fotos else "",
        "link_afiliado": link_afiliado(f"https://www.mercadolivre.com.br/p/{pid}"),
        "frete_gratis": "free_shipping" in str(melhor.get("shipping") or ""),
        "full": "fulfillment" in str(melhor.get("shipping") or ""),
        "vendedores": len(itens),
    }


def mais_vendidos(cat, quantos=5, preco_max=500, pular=None, info=None):
    r = _get(f"/highlights/MLB/category/{cat}")
    if r.status_code != 200:
        print(f"❌ Mais vendidos {cat}: {r.status_code}")
        return []
    nome_cat, categoria, pct = info or CATEGORIAS.get(cat, (cat, "lar", 9.0))
    saida = []
    for c in r.json().get("content", []):
        if c.get("type") != "PRODUCT":
            continue
        if pular and pular(f"ml{c['id']}"):
            continue
        o = produto(c["id"], categoria, c.get("position"), nome_cat, pct)
        if o and o["preco"] <= preco_max and o["imagem"]:
            saida.append(o)
        if len(saida) >= quantos:
            break
    return saida


# ---------------------------------------------------------------- Busca do Zé (04/11/2026)
def buscar(termo, quantos=12):
    """Busca no catálogo do ML (/products/search; a busca aberta dá 403) e devolve ofertas no formato do robô,
    na ordem da busca. O ML não mostra nota nem vendas: a posição na busca entra no lugar ("posicao")."""
    r = _get("/products/search", status="active", site_id="MLB", q=termo, limit=min(quantos, 50))
    if r.status_code != 200:
        raise RuntimeError(f"busca no catálogo respondeu {r.status_code}: {r.text[:150]}")
    ids = [x["id"] for x in r.json().get("results", []) if x.get("id")][:quantos]
    from concurrent.futures import ThreadPoolExecutor

    def um(par):
        pos, pid = par
        try:
            o = produto(pid, "busca", pos, "busca")
        except Exception as e:
            print(f"⚠️  ML {pid}: {str(e)[:80]}")
            return None
        if o:
            o["info_txt"] = f"{pos}º na busca do Mercado Livre"
        return o
    with ThreadPoolExecutor(6) as ex:
        return [o for o in ex.map(um, enumerate(ids, 1)) if o and o["imagem"]]


# ---------------------------------------------------------------- uso no garimpo
CATEGORIAS_POR_GARIMPO = int(os.getenv("ML_CATEGORIAS_POR_GARIMPO", "3"))
PRODUTOS_POR_CATEGORIA = int(os.getenv("ML_PRODUTOS_POR_CATEGORIA", "10"))
SUBCATEGORIAS_POR_CATEGORIA = int(os.getenv("ML_SUBCATEGORIAS", "6"))
POR_GARIMPO = int(os.getenv("ML_POR_GARIMPO", "8"))


def configurado():
    return ligado() and os.getenv("ML_ATIVO", "1") != "0"


def _categorias_da_vez():
    """Rodízio: a cada rodada pega as próximas categorias da lista (pela hora do dia), para variar o feed."""
    from datetime import datetime
    ids = list(CATEGORIAS)
    ini = (datetime.utcnow().timetuple().tm_yday * 24 + datetime.utcnow().hour) * CATEGORIAS_POR_GARIMPO % len(ids)
    return [ids[(ini + i) % len(ids)] for i in range(CATEGORIAS_POR_GARIMPO)]


def _subcategorias(cat):
    """Subcategorias sorteadas da categoria (o ranking geral é dominado por produto comum, tipo refil e
    alvejante; o ranking de cada subcategoria mostra os achados de nicho). Devolve [(id, nome)]."""
    import random
    r = _get(f"/categories/{cat}")
    filhas = [(c["id"], c["name"]) for c in (r.json().get("children_categories") or [])] if r.status_code == 200 else []
    random.shuffle(filhas)
    return filhas[:SUBCATEGORIAS_POR_CATEGORIA]


PALAVRAS_POR_GARIMPO = int(os.getenv("ML_PALAVRAS_POR_GARIMPO", "6"))


def _categoria_da_palavra(palavra):
    """Termo da busca do Zé → categoria-folha do ML (ex.: "luz led arvore" → Pisca-piscas). Devolve (id, nome, pct)."""
    r = _get("/sites/MLB/domain_discovery/search", q=palavra, limit=1)
    if r.status_code != 200 or not r.json():
        return None
    d = r.json()[0]
    pct = 10.0
    c = _get(f"/categories/{d['category_id']}")
    if c.status_code == 200:
        raiz = (c.json().get("path_from_root") or [{}])[0].get("id")
        pct = CATEGORIAS.get(raiz, (None, None, 10.0))[2]
    return d["category_id"], d.get("category_name") or palavra, pct


def candidatos(fila, ja_usado, julgar=None, palavras=None):
    """Mais vendidos do ML nas categorias da vez, com as regras do Garimpo (preço, comissão, IA de "uau").
    `ja_usado(fila, id)` é a regra de não repetir (garimpar.ja_usado)."""
    from . import config
    if not configurado() or config.PERFIL != "garimpo":
        return []
    ofs, recusas, vistos = [], {}, set()
    try:
        lista = []
        # 1º: os mesmos termos que o Zé está garimpando na Shopee (escolhidos pela curadoria por serem "uau"):
        # cada termo vira a categoria certinha do ML e entram os mais vendidos dela
        for nicho, palavra in (palavras or [])[:PALAVRAS_POR_GARIMPO]:
            achou = _categoria_da_palavra(palavra)
            if not achou:
                continue
            sub, nome_sub, pct = achou
            lista += mais_vendidos(sub, quantos=PRODUTOS_POR_CATEGORIA, preco_max=config.PRECO_MAXIMO,
                                   pular=lambda i: ja_usado(fila, i) or i in vistos, info=(nome_sub, nicho, pct))
            vistos.update(o["id"] for o in lista)
        # 2º: subcategorias sorteadas das categorias da vez
        for cat in _categorias_da_vez() if len(lista) < 20 else []:
            _, nicho, pct = CATEGORIAS[cat]
            for sub, nome_sub in _subcategorias(cat):
                lista += mais_vendidos(sub, quantos=PRODUTOS_POR_CATEGORIA, preco_max=config.PRECO_MAXIMO,
                                       pular=lambda i: ja_usado(fila, i) or i in vistos,
                                       info=(nome_sub, nicho, pct))
                vistos.update(o["id"] for o in lista)
        for o in lista:
            if o["categoria"] not in config.NICHO:
                recusas["fora do nicho"] = recusas.get("fora do nicho", 0) + 1
            # 08/11/2026 (Fred): sem mínimo de comissão no ML (o livro de R$ 41 que vendeu rendeu ~R$ 5)
            else:
                ofs.append(o)
    except Exception as e:
        print(f"::warning::Mercado Livre ficou de fora desta rodada: {e}")
        return []
    if julgar:
        julgar(ofs)
    from datetime import datetime
    from . import camadas
    if datetime.utcnow().strftime("%Y-%m-%d") <= config.ML_LANCAMENTO_ATE:
        # lançamento: produto conhecido (uau >= ML_LANCAMENTO_UAU) entra para o público ver que o ML chegou.
        # Com as camadas ligadas (src/camadas.py) ele entra como 🏷️ conhecido (sem o selo de achado);
        # sem elas, como antes: vale como achado do Instagram.
        for o in ofs:
            if o.get("uau", 0) >= config.ML_LANCAMENTO_UAU:
                o["lancamento_ml"] = True
                if not camadas.ligado():
                    o["uau_ia"] = o["uau"]
                    o["uau"] = max(o["uau"], config.UAU_MINIMO_INSTAGRAM)
    passa = [o for o in ofs if o.get("uau", 0) >= config.UAU_MINIMO_POSTAR or camadas.conhecido(o)]
    comuns = [o for o in ofs if o not in passa]
    ofs = sorted(passa,
                 key=lambda o: (o.get("uau_ia", o["uau"]), o["comissao"], -(o.get("posicao") or 99)), reverse=True)
    # variedade: no máximo 1 por família (nada de 3 câmeras) e só família que ainda tem vaga na fila
    from . import variedade
    from .garimpar import _limite_familia
    pend = variedade.contar_pendentes(fila)
    fams, diversos = set(), []
    for o in ofs:
        f = variedade.familia(o)
        if f in fams or pend.get(f, 0) >= _limite_familia(f):
            continue
        fams.add(f)
        diversos.append(o)
    escolhidas = []
    for o in diversos[:POR_GARIMPO]:
        ouro = o["uau"] >= config.NIVEIS["ouro"]["uau"] and o["comissao"] >= config.NIVEIS["ouro"]["comissao_rs"]
        o.update({"nivel": "ouro" if ouro else "prata", "origem_busca": "mercadolivre", "so_telegram": False,
                  "palavra": f"mercadolivre {o['info_txt']}",
                  "pontos": config.SHARK_PONTOS + (o["uau"] - config.SHARK_UAU) * config.PESO_UAU})
        escolhidas.append(o)
    for o in comuns[:8]:
        print(f"   🟡 comum (uau {o.get('uau', 0):.0f}): {o['nome'][:60]} · R$ {o['preco_fmt']}")
    print(f"🟡 Mercado Livre: {len(ofs) + len(comuns)} mais vendidos avaliados, {len(comuns)} comuns, "
          f"recusados {recusas}, entram {len(escolhidas)}: {[o['nome'][:35] for o in escolhidas]}")
    return escolhidas


def vagas_hoje(fila, campo, maximo, hoje):
    """Quantas ofertas do ML ainda cabem no dia no canal do `campo` ("postado_em" IG, "telegram_em" Telegram)."""
    ja = sum(1 for o in fila["ofertas"].values()
             if o.get("plataforma") == "mercadolivre" and str(o.get(campo) or "").startswith(hoje))
    return max(0, maximo - ja)


def _previa(pasta="previa_ml"):
    """Gera a arte do post de 1 mais vendido por categoria, sem postar. Fica em previa_ml/ (artefato do workflow)."""
    from . import imagem
    Path(pasta).mkdir(exist_ok=True)
    linhas = []
    for n, cat in enumerate(list(CATEGORIAS)[:6], 1):
        ofs = mais_vendidos(cat, quantos=1)
        if not ofs:
            continue
        o = ofs[0]
        try:
            imagem.gerar(o, f"{pasta}/{n}-{o['categoria']}.jpg")
        except Exception as e:
            print(f"⚠️  Arte de {o['nome']}: {e}")
        linhas.append(f"{n}. {o['nome']} · R$ {o['preco_fmt']}" + (f" (de R$ {_brl(o['preco_de'])}, -{o['desconto']}%)" if o["preco_de"] else "")
                      + f" · Top {o['posicao']} em {CATEGORIAS[cat][0]} · comissão R$ {o['comissao']:.2f} · {o['vendedores']} vendedores"
                      + (" · frete grátis" if o["frete_gratis"] else "") + f"\n   {o['link_afiliado']}")
    texto = "\n".join(linhas)
    Path(f"{pasta}/lista.txt").write_text(texto)
    print(texto)
    # tenta a nota do anúncio (se o ML liberar, entra no filtro de nota ≥4,7)
    r = _get("/reviews/item/MLB7896357598")
    print(f"Nota por anúncio (/reviews/item): {r.status_code} · {r.text[:200]}")


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "status"
    if acao == "conectar":
        _conectar()
    elif acao == "previa":
        _previa()
    elif acao == "busca":
        _status()
        _busca(" ".join(sys.argv[2:]) or "garrafa termica")
        if _env("ML_REFRESH_TOKEN"):
            _sonda(" ".join(sys.argv[2:]) or "garrafa termica")
    else:
        _status()
