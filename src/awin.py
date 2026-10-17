"""Shark Ninja BR pela Awin (feed de produtos do programa de afiliados).

Diferente da Shopee e da AliExpress, aqui não há busca por palavra-chave nem vendas/nota: o
programa da marca tem um catálogo pequeno (feed CSV da Awin) e cada produto já vem com o link de
afiliado pronto (aw_deep_link). Por isso a Shark Ninja entra no robô por um caminho próprio:

- as regras da Shopee (vendas, nota, teto de preço) não valem — são produtos da marca oficial;
- cada conta fica com o seu nicho: Garimpo VIP = casa e cozinha (aspiradores, air fryer, etc.),
  Ana Novo Achados = cabelo (secadores e modeladores);
- no máximo SHARK_POR_GARIMPO produtos novos entram na fila por rodada, e há limite diário de
  postagem (ver postar.py e telegram_ofertas.py), para a marca não dominar a página;
- antes de postar, o preço e o estoque são conferidos de novo no feed (conferir()).

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

PLATAFORMA = "sharkninja"
LOJA = "Shark-Ninja BR"
MARCA = "Shark Ninja"

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
                        r"escova de reposicao|pecas?|acessorio avulso)\b")
# Produto de cabelo: vai para a Ana. O resto é casa e cozinha: vai para o Garimpo VIP.
_CABELO = re.compile(r"\b(secador|secadores|modelador|modeladores|flexstyle|speedstyle|hyperair|"
                     r"alisador|alisadora|cachos|cabelo|cabelos|hair|styler|babyliss|escova secadora)\b")


def _tipo(nome):
    """Primeira palavra do nome que não seja a marca ("Shark Aspirador Vertical" → "aspirador")."""
    for p in re.findall(r"[a-z0-9]+", _sem_acento(nome)):
        if p not in ("shark", "ninja") and len(p) > 2:
            return p
    return "shark ninja"


def categoria_do_produto(nome, categoria_feed=""):
    """'cabelo' (Ana) ou 'lar' (Garimpo VIP). Devolve None se for acessório/reposição."""
    t = _sem_acento(f"{nome} {categoria_feed}")
    if _REPOSICAO.search(_sem_acento(nome)):
        return None
    return "cabelo" if _CABELO.search(t) else "lar"


def normalizar(l):
    """Linha do feed → oferta no formato do robô (mesmos campos de shopee/aliexpress)."""
    nome = " ".join(_SIMBOLOS.sub("", l.get("product_name", "")).split())
    preco = _preco(l.get("search_price") or l.get("store_price") or l.get("display_price"))
    antigo = _preco(l.get("product_price_old") or l.get("rrp_price"))
    desconto = round((1 - preco / antigo) * 100) if antigo > preco > 0 else 0
    imagem = l.get("large_image") or l.get("merchant_image_url") or l.get("aw_image_url") or ""
    pid = l.get("aw_product_id") or l.get("merchant_product_id") or ""
    cat = categoria_do_produto(nome, l.get("merchant_category") or l.get("category_name") or "")
    o = {
        "id": f"sn{pid}",
        "nome": nome,
        "categoria": cat,
        "palavra": _tipo(nome),
        "preco": preco,
        "preco_fmt": f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "preco_de": round(antigo, 2) if antigo > preco else None,
        "desconto": desconto,
        "comissao": round(preco * config.AWIN_COMISSAO_PCT / 100, 2),
        "comissao_pct": config.AWIN_COMISSAO_PCT,
        "vendas": 0,                     # o feed não traz vendas nem nota: a arte mostra "loja oficial"
        "nota": 0.0,
        "loja": LOJA,
        "marca": (l.get("brand_name") or MARCA).strip() or MARCA,
        "voltagem": voltagem(nome),
        "plataforma": PLATAFORMA,
        "imagem": imagem,
        "link_afiliado": l.get("aw_deep_link", ""),
        "descricao": re.sub(r"\s+", " ", l.get("description", ""))[:500],
        "em_estoque": _em_estoque(l),
    }
    from .precos import ajustar_de
    return ajustar_de(o)


def motivo_recusa(o):
    """Corte duro da Shark Ninja (sem teto de preço, sem vendas/nota)."""
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
            k = (o["categoria"], _chave_modelo(o["nome"]))
            if k not in melhores or (_PREF_VOLT.get(o["voltagem"], 1), o["preco"]) < (
                    _PREF_VOLT.get(melhores[k]["voltagem"], 1), melhores[k]["preco"]):
                melhores[k] = o
        variantes = len(ofertas) - len(melhores)
        ofertas = [o for o in ofertas if melhores[(o["categoria"], _chave_modelo(o["nome"]))] is o]
        print(f"🦈 Shark Ninja (Awin): {len(ofertas)} produtos válidos no feed | recusados: {recusas}"
              f"{' | versões de voltagem repetidas: ' + str(variantes) if variantes else ''}")
        _cache["produtos"] = ofertas
    return _cache["produtos"]


# ---------------------------------------------------------------- uso no garimpo

def candidatos(fila, ja_usado):
    """Ofertas novas da Shark Ninja para este perfil (no máximo SHARK_POR_GARIMPO), prontas para a fila.
    `ja_usado(fila, id)` é a regra de não repetir (garimpar.ja_usado)."""
    if not configurado():
        return []
    try:
        todas = produtos()
    except Exception as e:
        print(f"::warning::{e} A Shark Ninja fica de fora desta rodada.")
        return []
    do_perfil = [o for o in todas if o["categoria"] in config.NICHO and not ja_usado(fila, o["id"])]
    # entra primeiro o que está em promoção e o que paga mais; o resto rodiza porque ja_usado bloqueia o que já saiu
    do_perfil.sort(key=lambda o: (o["desconto"], o["comissao"]), reverse=True)
    escolhidas = []
    for o in do_perfil[:config.SHARK_POR_GARIMPO]:
        o = dict(o)
        o.update({"uau": config.SHARK_UAU, "nivel": "ouro", "origem_busca": "marca",
                  "pontos": config.SHARK_PONTOS, "so_telegram": False})
        escolhidas.append(o)
    print(f"🦈 Shark Ninja para o perfil {config.PERFIL}: {len(do_perfil)} disponíveis, {len(escolhidas)} entram na rodada.")
    return escolhidas


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
    try:
        linhas = baixar_linhas()
        print(f"::notice::Feed: {len(linhas)} linhas | colunas: {', '.join(linhas[0].keys()) if linhas else '(vazio)'}")
        for linha in linhas:
            o = normalizar(linha)
            m = motivo_recusa(o)
            if m:
                print(f"::notice::RECUSADO ({m}) | {o['nome'][:55]} | in_stock={linha.get('in_stock', '?')!r} | "
                      f"preço={o['preco']} | foto {'ok' if o['imagem'] else 'FALTA'} | link {'ok' if o['link_afiliado'] else 'FALTA'}")
        for o in produtos():
            print(f"::notice::[{o['categoria']}] {o['nome'][:60]} | R$ {o['preco_fmt']}"
                  f"{' (de R$ ' + str(o['preco_de']) + ')' if o['preco_de'] else ''} | comissão R$ {o['comissao']:.2f} | "
                  f"foto {'ok' if o['imagem'] else 'FALTA'} | link {'ok' if o['link_afiliado'] else 'FALTA'}"
                  f"{' | ' + o['voltagem'] if o['voltagem'] else ''}")
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
