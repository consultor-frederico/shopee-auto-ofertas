"""🔗 Link do Zé: a pessoa manda no direct o link de um produto (dela mesma ou de outro afiliado) e o Zé devolve
o MESMO produto, na MESMA loja, pelo link de afiliado do Garimpo VIP.

27/11/2026 (Fred: "a pessoa mandar o link e vc reenviar o de afiliado"). Regra de 26/11: o Zé fica na loja que
a pessoa escolheu — não troca o produto nem a loja.

O que cada loja permite (sem nada manual):
- Shopee: API de afiliados (productOfferV2 + generateShortLink). Link curto s.shopee/shope.ee é aberto antes.
  Produto fora do programa: gera só o link curto marcado (sem cartão).
- AliExpress: API de afiliados (productdetail.get; se o produto não vier, link.generate). Links curtos
  (s.click / a.aliexpress) são abertos antes.
- Mercado Livre: o programa NÃO tem API para gerar link; o robô usa o endereço limpo do produto + a etiqueta
  garimpovip (o mesmo de todo o garimpo). meli.la e /social/ de outro afiliado: abre e procura o produto (MLB…).
- Marcas da Awin (Arno, Shark-Ninja, VX Case, Lego, Lauri): produto do feed (link pronto) ou deeplink
  awin1.com/cread.php com o nosso id de afiliado (só lojas em que o Garimpo está aprovado).
- Amazon, Shein, Magalu, Temu, Kabum…: o Garimpo não é afiliado → o Zé diz isso e se oferece para procurar.

Ligado no direct do Instagram por src/busca_ze.rodar_dms (chave LINK_ZE_ATIVO no workflow 3).
Teste sem enviar nada: workflow 19 com termos "link: URL URL" (ou python -m src.link_ze URL).
"""
import os
import re
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

from . import config

ATIVO = os.getenv("LINK_ZE_ATIVO", "1") == "1"
CANAL = "zelink"   # subId da Shopee: vendas vindas do link devolvido no direct
MAX_LINKS = 3
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}

DOMINIOS = [   # (loja, pedaço do domínio)
    ("shopee", r"shopee\.com\.br|shope\.ee|shp\.ee"),
    ("mercadolivre", r"mercadolivre\.com\.br|mercadolibre\.com|meli\.la|mercadolivre\.com\b"),
    ("aliexpress", r"aliexpress\.(?:com|us)|aliexpress\.ru"),
    ("awin", r"awin1\.com|awin\.com"),
]
FORA = [   # lojas em que o Garimpo não é afiliado (nome que o Zé fala)
    ("Amazon", r"amazon\.com|amzn\.to|\ba\.co/"), ("Shein", r"shein\.(?:com|top)|shein\.com\.br"),
    ("Magalu", r"magazineluiza|magalu\.com|maga\.lu"), ("Temu", r"temu\.(?:com|to)"),
    ("Kabum", r"kabum\.com"), ("Americanas", r"americanas\.com"), ("Casas Bahia", r"casasbahia\.com"),
    ("TikTok Shop", r"tiktok\.com/.*(?:shop|product)|vt\.tiktok"),
]
RE_URL = re.compile(r"(?:https?://|\b(?:www\.)?(?=(?:s\.shopee\.com\.br|shope\.ee|meli\.la|s\.click\.aliexpress\.com|"
                    r"a\.aliexpress\.com|shopee\.com\.br|mercadolivre\.com\.br|produto\.mercadolivre\.com\.br|"
                    r"pt\.aliexpress\.com|amzn\.to|amazon\.com\.br)/))[^\s<>\"']+", re.I)

INTRO = ("Oi! 🤠 Prontinho! Esse é o mesmo produto, na mesma loja, agora pelo link do Garimpo VIP 👇\n"
         "(link de afiliado: você paga o mesmo e ajuda o Garimpo a continuar garimpando ⛏️)")
INTRO_VARIOS = INTRO.replace("Esse é o mesmo produto", "Esses são os mesmos produtos")
SO_LINK = ("Oi! 🤠 Prontinho! Aqui está o mesmo produto {loja} pelo link do Garimpo VIP 👇\n\n{link}\n\n"
           "(link de afiliado: você paga o mesmo e ajuda o Garimpo a continuar garimpando ⛏️)")
LOJA_FORA = ("Oi! 🤠 Aqui é o Zé Garimpo. Na {loja} eu ainda não tenho link 😅 Eu garimpo na Shopee, no Mercado "
             "Livre e na AliExpress. Se quiser, me manda o nome do produto que eu procuro pra você ⛏️")
NAO_ABRIU = ("Oi! 🤠 Aqui é o Zé Garimpo. Não consegui abrir esse link {loja} 😕 Me manda o nome do produto "
             "que eu procuro lá pra você ⛏️")
NOME_LOJA = {"shopee": "da Shopee", "mercadolivre": "do Mercado Livre", "aliexpress": "da AliExpress"}


# ------------------------------------------------------------------ achar os links
def links(texto):
    """Links de produto na mensagem (no máximo 3), na ordem em que aparecem."""
    vistos = []
    for m in RE_URL.finditer(texto or ""):
        u = m.group(0).rstrip(".,;!)]}")
        if not u.lower().startswith("http"):
            u = "https://" + u
        if u not in vistos and (loja_do_link(u) or _fora(u)):
            vistos.append(u)
    return vistos[:MAX_LINKS]


def tem_link(texto):
    return bool(links(texto))


def _host(url):
    return (urlparse(url).netloc or "").lower()


def loja_do_link(url):
    h = _host(url)
    for loja, rx in DOMINIOS:
        if re.search(rx, h):
            return loja
    return _marca_do_dominio(h)


def _fora(url):
    alvo = _host(url) + urlparse(url).path
    return next((nome for nome, rx in FORA if re.search(rx, alvo, re.I)), None)


def _abrir(url):
    """Segue os redirecionamentos do link curto. Devolve (endereço final, html, todos os endereços)."""
    try:
        r = requests.get(url, headers=UA, timeout=25, allow_redirects=True)
        caminho = [h.url for h in r.history] + [r.url]
        return r.url, r.text[:400000], caminho
    except Exception as e:
        print(f"⚠️  Link do Zé: não abri {url} ({str(e)[:120]})")
        return url, "", [url]


def _og(html, prop):
    m = (re.search(rf'property=["\']og:{prop}["\'][^>]*content=["\']([^"\']+)', html)
         or re.search(rf'content=["\']([^"\']+)["\'][^>]*property=["\']og:{prop}', html))
    return unquote(m.group(1)).strip() if m else ""


# ------------------------------------------------------------------ Shopee
def _shopee(url):
    from . import vale_a_pena, vendas
    from .garimpar import normalizar
    from . import shopee
    final = vale_a_pena._resolver(url)
    ids = vale_a_pena._ids(final)
    if ids:
        try:
            nos = shopee.buscar_por_item(ids[1])
            if nos and nos[0].get("offerLink"):
                o = normalizar(nos[0], "link_ze", "")
                if ids[0] and not o.get("loja_id"):
                    o["loja_id"] = ids[0]
                return {"oferta": o}
        except Exception as e:
            print(f"⚠️  Link do Zé: Shopee não trouxe o item {ids[1]} ({str(e)[:120]})")
        origem = f"https://shopee.com.br/product/{ids[0]}/{ids[1]}" if ids[0] else final
    else:
        origem = final.split("?")[0]
    try:   # produto fora da lista da API ou página da loja: só o link curto marcado
        curto = vendas.link_curto(origem, [config.PERFIL, CANAL])
        if curto.startswith("https://"):
            return {"link": curto, "nome": vale_a_pena._nome_do_link(final)}
    except Exception as e:
        print(f"⚠️  Link do Zé: Shopee não gerou link curto ({str(e)[:120]})")
    return None


# ------------------------------------------------------------------ AliExpress
def _id_aliexpress(url):
    u = unquote(unquote(url))
    m = re.search(r"(?<!\d)(100\d{13})(?!\d)", u)   # id do produto (1005…); o 3256… do link curto é outro id
    if m:
        return m.group(1)
    m = (re.search(r"/item/(?:\d+/)?(\d{8,})\.html", u) or re.search(r"[?&](?:productId|product_id|itemId)=(\d{8,})", u)
         or re.search(r"/i/(\d{8,})\.html", u))
    return m.group(1) if m else None


def _aliexpress(url):
    from . import aliexpress
    if not aliexpress.configurado():
        return None
    pid = _id_aliexpress(url)
    if not pid:
        final, html, caminho = _abrir(url)
        todos = " ".join(caminho) + " " + html[:80000]
        pid = (re.search(r"(?<!\d)(100\d{13})(?!\d)", unquote(unquote(todos))) or [None, None])[1] \
            or next((p for p in map(_id_aliexpress, caminho) if p), None)
    if not pid:
        return None
    track = aliexpress._env("ALIEXPRESS_TRACKING_ID")
    try:
        metodo = "aliexpress.affiliate.productdetail.get"
        dados = aliexpress.chamar(metodo, product_ids=pid, target_currency="BRL", target_language="PT",
                                  country="BR", tracking_id=track)
        resp = (dados.get(metodo.replace(".", "_") + "_response") or {}).get("resp_result") or {}
        ps = ((resp.get("result") or {}).get("products") or {}).get("product") or []
        if ps and ps[0].get("promotion_link"):
            return {"oferta": aliexpress.normalizar(ps[0], "link_ze", "")}
        print(f"⚠️  Link do Zé: AliExpress sem detalhe do {pid} (resp {resp.get('resp_code')} {resp.get('resp_msg')})")
    except Exception as e:
        print(f"⚠️  Link do Zé: AliExpress detalhe {pid}: {str(e)[:160]}")
    try:   # produto fora do programa de afiliados do item: link de afiliado da página mesmo assim
        metodo = "aliexpress.affiliate.link.generate"
        dados = aliexpress.chamar(metodo, promotion_link_type=0, tracking_id=track,
                                  source_values=f"https://pt.aliexpress.com/item/{pid}.html")
        resp = (dados.get(metodo.replace(".", "_") + "_response") or {}).get("resp_result") or {}
        pl = ((resp.get("result") or {}).get("promotion_links") or {}).get("promotion_link") or []
        if pl and pl[0].get("promotion_link"):
            return {"link": pl[0]["promotion_link"]}
        print(f"⚠️  Link do Zé: AliExpress não gerou link do {pid} (resp {resp.get('resp_code')} {resp.get('resp_msg')})")
    except Exception as e:
        print(f"⚠️  Link do Zé: AliExpress link.generate {pid}: {str(e)[:160]}")
    return None


# ------------------------------------------------------------------ Mercado Livre
def _ids_ml(texto):
    """(catálogo, anúncio): /p/MLB123 e MLB-123 / MLB123 / item_id=MLB123."""
    t = unquote(texto or "")
    cat = re.search(r"/p/(MLB\d{5,})", t)
    item = re.search(r"\bMLB-?(\d{6,})", t.replace("/p/MLB", "/p/X"))
    return (cat.group(1) if cat else None), (f"MLB{item.group(1)}" if item else None)


def _mercadolivre(url):
    from . import mercadolivre
    cat, item = _ids_ml(url)
    final, html, caminho = (url, "", [url])
    if not (cat or item):   # meli.la, /social/ de outro afiliado: abre e procura o produto
        final, html, caminho = _abrir(url)
        for c in caminho:
            cat, item = _ids_ml(c)
            if cat or item:
                break
        if not (cat or item) and html:
            canon = re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', html)
            cat, item = _ids_ml((canon.group(1) if canon else "") + " " + _og(html, "url"))
            if not (cat or item):
                cat, item = _ids_ml(html[:200000])   # 1º produto citado na página
    if not (cat or item):
        return None
    if cat:
        link = mercadolivre.link_afiliado(f"https://www.mercadolivre.com.br/p/{cat}")
        nome, foto = "", ""
        try:
            if mercadolivre.configurado():
                r = mercadolivre._get(f"/products/{cat}")
                if r.status_code == 200:
                    p = r.json()
                    nome = p.get("name") or ""
                    foto = next((f.get("url") for f in p.get("pictures") or [] if f.get("url")), "")
        except Exception as e:
            print(f"⚠️  Link do Zé: catálogo ML {cat}: {str(e)[:120]}")
    else:
        alvo = next((c for c in caminho if f"MLB-{item[3:]}" in c or item in c), None)
        if alvo and "mercadolivre.com.br" in _host(alvo) and "/social/" not in alvo:
            link = mercadolivre.link_afiliado(alvo.split("#")[0])
        else:
            link = mercadolivre.link_afiliado(f"https://produto.mercadolivre.com.br/MLB-{item[3:]}")
        slug = re.search(r"MLB-\d+-([^/?#]+?)(?:-_JM)?(?:[/?#]|$)", unquote(alvo or url))
        nome = _og(html, "title") if html and "/social/" not in final else ""
        nome = nome or (slug.group(1).replace("-", " ") if slug else "")
        foto = _og(html, "image") if html and "/social/" not in final else ""
    return {"oferta": {"id": f"ml{cat or item}", "nome": nome or "Produto do Mercado Livre", "plataforma": "mercadolivre",
                       "link_afiliado": link, "imagem": foto, "preco_fmt": ""}}


# ------------------------------------------------------------------ marcas da Awin
_feed = []


def _produtos_awin():
    from . import awin
    if not _feed:
        try:
            if awin.configurado():
                _feed.extend(awin.produtos())
        except Exception as e:
            print(f"⚠️  Link do Zé: feed da Awin ({str(e)[:120]})")
    return _feed


SOCIAIS = r"instagram\.com|facebook\.com|fb\.me|youtu|wa\.me|whatsapp\.com|t\.me|tiktok\.com|google\.|github\.io|x\.com|twitter\.com"


def _marca_do_dominio(host):
    host = host.removeprefix("www.")
    if not host or re.search(SOCIAIS, host) or any(re.search(rx, host) for _, rx in DOMINIOS):
        return None
    for o in _produtos_awin():
        h = _host(o.get("pagina") or "").removeprefix("www.")
        if h and (h == host or host.endswith("." + h)):
            return o["plataforma"]
    return None


def _awin(url):
    alvo, pid = url, ""
    if re.search(r"awin1?\.com", _host(url)):   # link da Awin de outro afiliado: o produto está no ued ou no p
        q = parse_qs(urlparse(url).query)
        alvo = (q.get("ued") or [""])[0]
        pid = (q.get("p") or [""])[0] if "pclick" in url else ""
        if pid:
            o = next((o for o in _produtos_awin() if str(o["id"]).endswith(pid)), None)
            if o:
                return {"oferta": o}
        if not alvo:
            final, _, _ = _abrir(url)
            alvo = final if "awin" not in _host(final) else ""
        if not alvo:
            return None
    marca = loja_do_link(alvo)
    feed = [o for o in _produtos_awin() if o["plataforma"] == marca]
    if not feed:
        return None
    caminho = urlparse(alvo).path.rstrip("/").lower()
    o = next((o for o in feed if urlparse(o.get("pagina") or "").path.rstrip("/").lower() == caminho), None)
    if o:
        return {"oferta": o}
    for x in feed:   # deeplink com o nosso id: cread.php (awinmid/awinaffid) ou pclick (m/a) do feed
        q = parse_qs(urlparse(x.get("link_afiliado") or "").query)
        mid, aff = (q.get("awinmid") or q.get("m") or [""])[0], (q.get("awinaffid") or q.get("a") or [""])[0]
        if mid and aff:
            return {"link": f"https://www.awin1.com/cread.php?awinmid={mid}&awinaffid={aff}"
                            f"&ued={quote(alvo.split('#')[0], safe='')}"}
    return None


# ------------------------------------------------------------------ montar e responder
FONTES = {"shopee": _shopee, "aliexpress": _aliexpress, "mercadolivre": _mercadolivre}


def converter(url):
    """Devolve {"loja", "oferta" | "link" | "fora" | "falhou"} para um link."""
    fora = _fora(url)
    if fora:
        return {"loja": fora, "fora": True}
    loja = loja_do_link(url)
    try:
        r = FONTES.get(loja, _awin)(url)
    except Exception as e:
        print(f"⚠️  Link do Zé ({loja}): {str(e)[:200]}")
        r = None
    return dict(r or {"falhou": True}, loja=loja or "?")


def _cartao(o, link):
    from .busca_ze import _curto, _foto_cartao, _nome_loja
    preco = f" • R$ {o['preco_fmt']}" if o.get("preco_fmt") else " • preço do dia na página"
    c = {"title": _curto(o["nome"], 75),
         "subtitle": f"{_nome_loja(o)}{preco}{' • internacional' if o.get('internacional') else ''} • link de afiliado"[:80],
         "default_action": {"type": "web_url", "url": link},
         "buttons": [{"type": "web_url", "url": link, "title": "🛒 Ver o produto"}]}
    foto = _foto_cartao(o) if o.get("imagem") else ""
    if foto:
        c["image_url"] = foto
    return c


def link_final(r):
    from . import vendas
    return vendas.do_canal(r["oferta"], CANAL) if r.get("oferta") else r.get("link", "")


def responder(api, ig_id, autor, texto):
    """Troca os links da mensagem pelos do Garimpo e responde no direct.
    Devolve (ids das mensagens do robô, status, resumo para o registro)."""
    enviar = lambda msg: api._req("POST", f"{ig_id}/messages", json={"recipient": {"id": autor}, "message": msg})
    rs = [converter(u) for u in links(texto)]
    ok = [r for r in rs if r.get("oferta") or r.get("link")]
    ids, resumo = [], [f"{r['loja']}: " + (r["oferta"]["nome"][:70] if r.get("oferta") else
                                          r.get("link") or ("loja fora" if r.get("fora") else "não abriu")) for r in rs]
    if ok:
        cartoes = [r for r in ok if r.get("oferta")]
        soltos = [r for r in ok if not r.get("oferta")]
        if cartoes:
            ids.append(enviar({"text": INTRO_VARIOS if len(cartoes) > 1 else INTRO}))
            elementos = [_cartao(r["oferta"], link_final(r)) for r in cartoes]
            try:
                ids.append(enviar({"attachment": {"type": "template", "payload": {
                    "template_type": "generic", "elements": elementos}}}))
            except Exception as e:   # sem cartão: os links no texto
                print(f"⚠️  Cartão do link recusado ({e}); mandando o link no texto.")
                ids.append(enviar({"text": "\n\n".join(f"{c['title']}\n{c['buttons'][0]['url']}" for c in elementos)}))
        for r in soltos:
            ids.append(enviar({"text": SO_LINK.format(loja=NOME_LOJA.get(r["loja"], "da loja"), link=r["link"])}))
        status = "link_trocado"
    elif any(r.get("fora") for r in rs):
        ids.append(enviar({"text": LOJA_FORA.format(loja=next(r["loja"] for r in rs if r.get("fora")))}))
        status = "loja_fora"
    else:
        ids.append(enviar({"text": NAO_ABRIU.format(loja=NOME_LOJA.get(rs[0]["loja"], "") if rs else "")
                           .replace("link  😕", "link 😕")}))
        status = "nao_abriu"
    return [(i or {}).get("message_id") for i in ids], status, resumo


if __name__ == "__main__":   # teste: python -m src.link_ze URL [URL...] → mostra o que o Zé mandaria (não envia)
    import sys
    for arg in sys.argv[1:] or ["https://shopee.com.br/product/335317330/21199078523"]:
        print(f"\n🔗 {arg}")
        if not links(arg):
            print("   (não é link de loja conhecida: o Zé segue a conversa normal)")
            continue
        for u in links(arg):
            r = converter(u)
            if r.get("oferta"):
                o = r["oferta"]
                print(f"::notice::{r['loja']}: {o['nome'][:80]} | R$ {o.get('preco_fmt') or '?'} | "
                      f"foto {'sim' if o.get('imagem') else 'NÃO'} | {link_final(r)}")
            elif r.get("link"):
                print(f"::notice::{r['loja']}: só link → {r['link']}")
            elif r.get("fora"):
                print(f"::notice::{r['loja']}: loja fora → {LOJA_FORA.format(loja=r['loja'])}")
            else:
                print(f"::warning::{r['loja']}: não consegui converter → {NAO_ABRIU.format(loja=NOME_LOJA.get(r['loja'], ''))}")
