"""Marcas oficiais pela Awin (Shark Ninja BR, Arno BR): feed de produtos dos programas de afiliados.

Diferente da Shopee e da AliExpress, aqui não há busca por palavra-chave nem vendas/nota: cada
programa tem um catálogo pequeno (feed CSV da Awin) e cada produto já vem com o link de
afiliado pronto (aw_deep_link). Um feed só traz todas as marcas (coluna merchant_name); a tabela de
marcas fica em src/marcas.py. As marcas entram no robô por um caminho próprio:

- as regras da Shopee (vendas, nota, teto de preço) não valem — são produtos da marca oficial;
- cada conta fica com o seu nicho: Garimpo VIP = casa e cozinha (aspiradores, air fryer, etc.),
  Ana Novo Achados = cabelo (secadores e modeladores);
- no máximo SHARK_POR_GARIMPO produtos novos de cada marca entram na fila por rodada, e há limite
  diário de postagem por marca (ver postar.py e telegram_ofertas.py), para a marca não dominar a página;
- antes de postar, o preço e o estoque são conferidos de novo no feed (conferir()). Marca com feed
  parado (Arno: conferir_site) tem o preço conferido na própria loja (VTEX), ao entrar na fila e antes de postar.

Segredos: AWIN_FEED_URL (URL do feed gerada em Ferramentas → Crie um Feed, CSV com vírgula e gzip;
contém a chave da Awin, por isso nunca vai para o log). Ligue com AWIN_ATIVO=1.
Teste: python -m src.awin
"""
import csv
import gzip
import io
import re
import sys
import unicodedata

import requests

from . import config
from .marcas import MARCAS

_cache = {"produtos": None}


def configurado():
    return config.AWIN_ATIVO and bool(config.AWIN_FEED_URL)


# ---------------------------------------------------------------- leitura do feed

def _texto(b):
    if b[:2] == b"\x1f\x8b":                       # gzip
        b = gzip.decompress(b)
    return b.decode("utf-8-sig", errors="replace")


def baixar_linhas():
    """Baixa o feed e devolve a lista de linhas (dicionários por nome de coluna)."""
    try:
        r = requests.get(config.AWIN_FEED_URL, timeout=90)
        r.raise_for_status()
    except requests.RequestException as e:
        # a URL leva a chave da Awin: nunca mostrar o endereço, só o tipo do erro
        raise RuntimeError(f"Awin: falha ao baixar o feed ({type(e).__name__}"
                           f"{' ' + str(e.response.status_code) if getattr(e, 'response', None) is not None else ''}).") from None
    leitor = csv.DictReader(io.StringIO(_texto(r.content)))
    return [{(k or "").strip(): (v or "").strip() for k, v in linha.items()} for linha in leitor]


def _preco(v):
    """'1.299,90', '1,299.90', '599.00', 'R$ 599' → 599.0 (aceita os dois formatos)."""
    s = re.sub(r"[^\d.,]", "", str(v or ""))
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _em_estoque(l):
    v = (l.get("in_stock") or "").strip().lower()
    return v not in ("0", "false", "no", "não", "nao", "n", "out of stock")   # vazio = assume que tem


_SIMBOLOS = re.compile(r"[®™©℠]")


def _sem_acento(t):
    return unicodedata.normalize("NFKD", _SIMBOLOS.sub("", t or "")).encode("ascii", "ignore").decode().lower()


# Voltagem: o mesmo produto vem em versões 110V e 220V (e Bivolt). Aparece no título e no aviso do preço,
# e só uma versão por produto entra no robô (preferência: Bivolt, 110V/127V, 220V).
_VOLT = re.compile(r"\b(110|127|220)\s?v\b|\bbivolt\b|\b110\s?/\s?220\s?v\b", re.I)
_PREF_VOLT = {"Bivolt": 0, "110V": 1, "127V": 1, "220V": 2, "": 1}


def voltagem(nome):
    m = _VOLT.search(_SIMBOLOS.sub("", nome or ""))
    if not m:
        return ""
    t = m.group(0).lower().replace(" ", "")
    return "Bivolt" if "bivolt" in t or "/" in t else t.upper()


def _chave_modelo(nome):
    """Nome sem voltagem: variantes 110V/220V do mesmo produto têm a mesma chave."""
    return " ".join(_VOLT.sub("", _sem_acento(nome)).split())


# Peça de reposição/acessório solto: commodity, não é achado
_REPOSICAO = re.compile(r"\b(refil|refis|filtro|filtros|reposicao|substituicao|bateria|kit de escovas|"
                        r"escova de reposicao|pecas?|acessorio avulso|pano|panos|estojo|potes?|case|capa)\b")
# Produto de cabelo: vai para a Ana. O resto é casa e cozinha: vai para o Garimpo VIP.
_CABELO = re.compile(r"\b(secador|secadores|modelador|modeladores|flexstyle|speedstyle|hyperair|"
                     r"alisador|alisadora|cachos|cabelo|cabelos|hair|styler|babyliss|escova secadora)\b")


_PALAVRAS_MARCA = {"shark", "ninja", "arno"}


def _tipo(nome, plataforma):
    """Primeira palavra do nome que não seja a marca ("Shark Aspirador Vertical" → "aspirador")."""
    for p in re.findall(r"[a-z0-9]+", _sem_acento(nome)):
        if p not in _PALAVRAS_MARCA and len(p) > 2:
            return p
    return MARCAS[plataforma]["nome"].lower()


def plataforma_da_linha(l):
    """Qual marca é a linha do feed, pelo nome do anunciante. Feed antigo sem a coluna = Shark Ninja."""
    anunciante = _sem_acento(l.get("merchant_name", ""))
    if not anunciante:
        return "sharkninja"
    for p, m in MARCAS.items():
        if any(a in anunciante for a in m["anunciante"]):
            return p
    return None   # anunciante que o robô ainda não conhece (falta linha em src/marcas.py)


def categoria_do_produto(nome, categoria_feed=""):
    """'cabelo' (Ana) ou 'lar' (Garimpo VIP). Devolve None se for acessório/reposição."""
    t = _sem_acento(f"{nome} {categoria_feed}")
    if _REPOSICAO.search(_sem_acento(nome)):
        return None
    return "cabelo" if _CABELO.search(t) else "lar"


def normalizar(l):
    """Linha do feed → oferta no formato do robô (mesmos campos de shopee/aliexpress)."""
    plat = plataforma_da_linha(l) or "desconhecida"
    m = MARCAS.get(plat, {"nome": l.get("merchant_name", ""), "loja": l.get("merchant_name", ""), "prefixo": "xx"})
    nome = " ".join(_SIMBOLOS.sub("", l.get("product_name", "")).split())
    preco = _preco(l.get("search_price") or l.get("store_price") or l.get("display_price"))
    antigo = _preco(l.get("product_price_old") or l.get("rrp_price"))
    desconto = round((1 - preco / antigo) * 100) if antigo > preco > 0 else 0
    imagem = l.get("large_image") or l.get("merchant_image_url") or l.get("aw_image_url") or ""
    pid = l.get("aw_product_id") or l.get("merchant_product_id") or ""
    cat = categoria_do_produto(nome, l.get("merchant_category") or l.get("category_name") or "")
    o = {
        "id": f"{m['prefixo']}{pid}",
        "nome": nome,
        "categoria": cat,
        "palavra": _tipo(nome, plat) if plat in MARCAS else "",
        "preco": preco,
        "preco_fmt": f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "preco_de": round(antigo, 2) if antigo > preco else None,
        "desconto": desconto,
        "comissao": round(preco * config.AWIN_COMISSAO_PCT / 100, 2),
        "comissao_pct": config.AWIN_COMISSAO_PCT,
        "vendas": 0,                     # o feed não traz vendas nem nota: a arte mostra "loja oficial"
        "nota": 0.0,
        "loja": m["loja"],
        "marca": (l.get("brand_name") or m["nome"]).strip() or m["nome"],
        "voltagem": voltagem(nome),
        "plataforma": plat,
        "imagem": imagem,
        "imagens_feed": {k: l.get(k, "") for k in ("large_image", "merchant_image_url", "aw_image_url", "merchant_thumb_url") if l.get(k)},
        "link_afiliado": l.get("aw_deep_link", ""),
        "pagina": l.get("merchant_deep_link", ""),
        "descricao": re.sub(r"\s+", " ", l.get("description", ""))[:500],
        "em_estoque": _em_estoque(l),
    }
    from .precos import ajustar_de
    return ajustar_de(o)


def motivo_recusa(o):
    """Corte duro das marcas oficiais (sem teto de preço, sem vendas/nota)."""
    if o["plataforma"] not in MARCAS:
        return "anunciante sem cadastro em src/marcas.py"
    if not o["id"][2:]:
        return "sem id"
    if not o["link_afiliado"].startswith("https://") or not o["imagem"].startswith("http"):
        return "sem link ou imagem"
    if o["preco"] <= 0:
        return "sem preço"
    if not o["em_estoque"]:
        return "sem estoque"
    if len(o["nome"]) < 5:
        return "sem nome"
    if o["categoria"] is None:
        return "acessório ou reposição"
    return None


def produtos(forcar=False):
    """Todas as ofertas válidas do feed (cache por execução)."""
    if _cache["produtos"] is None or forcar:
        ofertas, recusas = [], {}
        for linha in baixar_linhas():
            o = normalizar(linha)
            m = motivo_recusa(o)
            if m:
                recusas[m] = recusas.get(m, 0) + 1
                continue
            ofertas.append(o)
        melhores = {}
        for o in ofertas:   # uma versão por produto (110V/220V): fica a de voltagem preferida, depois a mais barata
            k = (o["plataforma"], o["categoria"], _chave_modelo(o["nome"]))
            if k not in melhores or (_PREF_VOLT.get(o["voltagem"], 1), o["preco"]) < (
                    _PREF_VOLT.get(melhores[k]["voltagem"], 1), melhores[k]["preco"]):
                melhores[k] = o
        variantes = len(ofertas) - len(melhores)
        ofertas = [o for o in ofertas if melhores[(o["plataforma"], o["categoria"], _chave_modelo(o["nome"]))] is o]
        por_marca = {}
        for o in ofertas:
            por_marca[MARCAS[o["plataforma"]]["nome"]] = por_marca.get(MARCAS[o["plataforma"]]["nome"], 0) + 1
        print(f"🏬 Marcas (Awin): {len(ofertas)} produtos válidos no feed {por_marca} | recusados: {recusas}"
              f"{' | versões de voltagem repetidas: ' + str(variantes) if variantes else ''}")
        _cache["produtos"] = ofertas
    return _cache["produtos"]


# ---------------------------------------------------------------- uso no garimpo

def candidatos(fila, ja_usado):
    """Ofertas novas das marcas para este perfil (no máximo SHARK_POR_GARIMPO de cada), prontas para a fila.
    `ja_usado(fila, id)` é a regra de não repetir (garimpar.ja_usado)."""
    if not configurado():
        return []
    try:
        todas = produtos()
    except Exception as e:
        print(f"::warning::{e} As marcas oficiais ficam de fora desta rodada.")
        return []
    do_perfil = [o for o in todas if o["categoria"] in config.NICHO and not ja_usado(fila, o["id"])]
    # entra primeiro o que está em promoção e o que paga mais; o resto rodiza porque ja_usado bloqueia o que já saiu
    do_perfil.sort(key=lambda o: (o["desconto"], o["comissao"]), reverse=True)
    escolhidas, por_marca = [], {}
    for o in do_perfil:
        plat = o["plataforma"]
        if por_marca.get(plat, 0) >= config.SHARK_POR_GARIMPO:
            continue
        o = dict(o)
        if MARCAS[plat]["conferir_site"] and _conferir_site(o) in ("sumiu", "erro"):
            continue   # feed parado: só entra o que a loja confirma que existe, com o preço de hoje
        o.update({"uau": config.SHARK_UAU, "nivel": "ouro", "origem_busca": "marca",
                  "pontos": config.SHARK_PONTOS, "so_telegram": False})
        escolhidas.append(o)
        por_marca[plat] = por_marca.get(plat, 0) + 1
    print(f"🏬 Marcas para o perfil {config.PERFIL}: {len(do_perfil)} disponíveis, entram na rodada: "
          f"{ {MARCAS[p]['nome']: n for p, n in por_marca.items()} or 'nenhuma'}.")
    return escolhidas


_PAGINA_VTEX = re.compile(r"^(https?://[^/?#]+)/([^/?#]+)/p\b")


def _conferir_site(o):
    """Preço e estoque na loja da marca (VTEX), para quando o feed da Awin está parado.
    Atualiza o e devolve 'ok', 'mudou', 'sumiu' ou 'erro' (loja fora do ar / página fora do padrão)."""
    m = _PAGINA_VTEX.match(o.get("pagina") or "")
    if not m:
        return "erro"
    base, slug = m.groups()
    try:
        r = requests.get(f"{base}/api/catalog_system/pub/products/search/{slug}/p", timeout=30,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        produtos_site = r.json()
    except Exception as e:
        print(f"::warning::Não consegui conferir {o['id']} na loja ({type(e).__name__}).")
        return "erro"
    ofertas_site = [s["commertialOffer"] for p in produtos_site for i in p.get("items", [])
                    for s in i.get("sellers", []) if (s.get("commertialOffer") or {}).get("AvailableQuantity", 0) > 0
                    and (s["commertialOffer"].get("Price") or 0) > 0]
    if not ofertas_site:
        return "sumiu"
    melhor = min(ofertas_site, key=lambda c: c["Price"])
    antigo = o.get("preco") or 0
    preco, de = float(melhor["Price"]), float(melhor.get("ListPrice") or 0)
    o["preco"] = preco
    o["preco_fmt"] = f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    o["preco_de"] = round(de, 2) if de > preco else None
    o["desconto"] = round((1 - preco / de) * 100) if de > preco > 0 else 0
    o["comissao"] = round(preco * config.AWIN_COMISSAO_PCT / 100, 2)
    from .precos import ajustar_de
    ajustar_de(o)
    return "mudou" if abs(preco - antigo) >= 0.01 else "ok"


def conferir(o):
    """Confere preço e estoque no feed antes de postar. Devolve 'ok', 'mudou', 'subiu' ou 'sumiu'."""
    if not configurado():
        return "ok"
    try:
        atual = next((p for p in produtos() if p["id"] == o["id"]), None)
    except Exception as e:
        print(f"::warning::Não consegui conferir {o['id']} no feed ({type(e).__name__}); seguindo com o preço do garimpo.")
        return "ok"
    if atual is None:
        return "sumiu"     # saiu do feed, sem estoque ou sem preço
    antigo = o.get("preco") or 0
    from .precos import SUBIDA_MAX
    if MARCAS.get(o.get("plataforma"), {}).get("conferir_site"):
        o["link_afiliado"] = atual["link_afiliado"]
        situacao = _conferir_site(o)
        if situacao == "erro":
            print(f"::warning::{o['id']}: loja não respondeu; não posto com o preço do feed parado.")
            return "sumiu"
        if situacao != "sumiu" and antigo and o["preco"] > antigo * SUBIDA_MAX:
            return "subiu"
        return situacao
    if antigo and atual["preco"] > antigo * SUBIDA_MAX:
        return "subiu"
    mudou = abs(atual["preco"] - antigo) >= 0.01
    for k in ("preco", "preco_fmt", "preco_de", "desconto", "comissao", "link_afiliado"):
        o[k] = atual[k]
    return "mudou" if mudou else "ok"


if __name__ == "__main__":   # teste: python -m src.awin  (com AWIN_FEED_URL e AWIN_ATIVO=1)
    if not config.AWIN_FEED_URL:
        print("⏸️  Segredo AWIN_FEED_URL ainda não cadastrado.")
        sys.exit(0)
    config.AWIN_ATIVO = True

    def aviso_unico(titulo, linhas):   # o GitHub mostra só 10 anotações por passo: junta tudo em uma
        codificado = [l.replace("%", "%25").replace("\r", "").replace("\n", "%0A") for l in (linhas or ["(nenhum)"])]
        print(f"::notice title={titulo}::" + "%0A".join(codificado))
        for l in linhas:
            print(l)

    if "--previa" in sys.argv:   # legenda da IA e arte com a foto real de 2 produtos do perfil (não posta nada)
        import tempfile
        from pathlib import Path

        from . import imagem, legenda
        saida = []
        try:
            do_nicho = [o for o in produtos() if o["categoria"] in config.NICHO]
            alvo = [next(o for o in do_nicho if o["plataforma"] == p) for p in dict.fromkeys(o["plataforma"] for o in do_nicho)][:3]
            for o in alvo:
                o.update(uau=config.SHARK_UAU, nivel="ouro")
                t = legenda.gerar(o)
                o["titulo"], o["legenda"] = t["titulo"], t["legenda"]
                try:
                    foto = imagem._baixar_foto(o["imagem"])
                    pasta = Path(sys.argv[sys.argv.index("--salvar") + 1]) if "--salvar" in sys.argv else Path(tempfile.mkdtemp())
                    pasta.mkdir(parents=True, exist_ok=True)
                    arte = pasta / f"{config.PERFIL}_{o['id']}.jpg"
                    imagem.gerar(o, arte, foto=foto)
                    (pasta / f"{config.PERFIL}_{o['id']}.txt").write_text(
                        f"{o['titulo']}\n\n{o['legenda']}\n\n{o['link_afiliado'].split('?')[0]}\n", encoding="utf-8")
                    estado = f"arte ok ({arte.stat().st_size // 1024} KB, foto {foto.size[0]}x{foto.size[1]})"
                except Exception as e:
                    estado = f"ARTE FALHOU: {type(e).__name__} {str(e)[:150]}"
                tamanhos = []
                for coluna, url in o.get("imagens_feed", {}).items():   # qual coluna do feed traz a foto maior?
                    try:
                        f = imagem._baixar_foto(url)
                        tamanhos.append(f"{coluna}={f.size[0]}x{f.size[1]}")
                    except Exception as e:
                        tamanhos.append(f"{coluna}=erro {type(e).__name__}")
                saida.append("fotos do feed: " + ", ".join(tamanhos))
                saida.append(f"url da foto: {o['imagem']}")
                saida.append(f"página do produto: {o.get('pagina', '')}")
                m = re.search(r"^(https?://[^/]+)/arquivos/ids/(\d+)", o["imagem"])
                if m:   # loja VTEX: testa pedir a foto em tamanho maior pela URL
                    base, ident = m.groups()
                    for suf in (f"/arquivos/ids/{ident}", f"/arquivos/ids/{ident}-1000-1000", f"/arquivos/ids/{ident}-1000-1000/foto.jpg",
                                f"/arquivos/ids/{ident}-1500-1500/foto.jpg", f"/arquivos/ids/{ident}_1", f"/arquivos/ids/{ident}_2"):
                        try:
                            f = imagem._baixar_foto(base + suf)
                            saida.append(f"vtex {suf.split('ids/')[1]} = {f.size[0]}x{f.size[1]}")
                        except Exception as e:
                            saida.append(f"vtex {suf.split('ids/')[1]} = erro {type(e).__name__}")
                saida += [f"=== {o['nome']} | legenda: {t['fonte']}", f"título: {t['titulo']}", estado, t["legenda"], ""]
        except Exception as e:
            saida.append(f"ERRO: {type(e).__name__} {str(e)[:200]}")
        aviso_unico(f"Previa {config.PERFIL}", saida)
        sys.exit(0)

    try:
        linhas = baixar_linhas()
        aviso_unico("Feed", [f"{len(linhas)} linhas", "colunas: " + (", ".join(linhas[0].keys()) if linhas else "(vazio)")])
        recusados = []
        for linha in linhas:
            o = normalizar(linha)
            m = motivo_recusa(o)
            if m:
                recusados.append(f"RECUSADO ({m}) | {o['nome'][:55]} | in_stock={linha.get('in_stock', '?')!r} | "
                                 f"preço={o['preco']} | foto {'ok' if o['imagem'] else 'FALTA'} | "
                                 f"link {'ok' if o['link_afiliado'] else 'FALTA'}")
        aviso_unico("Recusados", recusados)
        validos = [f"[{MARCAS[o['plataforma']]['nome']} · {o['categoria']}] {o['nome'][:60]} | R$ {o['preco_fmt']}"
                   f"{' (de R$ ' + str(o['preco_de']) + ')' if o['preco_de'] else ''} | comissão R$ {o['comissao']:.2f}"
                   f"{' | ' + o['voltagem'] if o['voltagem'] else ''}" for o in produtos()]
        aviso_unico("Produtos que o robô usaria", validos)
        site = []   # marca com feed parado: compara o preço do feed com o da loja hoje
        for o in [o for o in produtos() if MARCAS[o["plataforma"]]["conferir_site"]][:8]:
            o, feed = dict(o), o["preco_fmt"]
            situacao = _conferir_site(o)
            site.append(f"{o['nome'][:55]} | feed R$ {feed} | loja hoje: "
                        + (f"R$ {o['preco_fmt']}" if situacao in ("ok", "mudou") else situacao.upper()))
        if site:
            aviso_unico("Preço na loja (feed parado)", site)
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
