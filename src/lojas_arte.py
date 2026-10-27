"""Identidade visual de cada loja: quem bate o olho na arte sabe de onde vem o produto.

- Shopee e AliExpress: a arte normal da conta, com o selo da loja (sacolinha laranja da Shopee, globo vermelho da
  AliExpress, que é sempre internacional).
- Marcas oficiais da Awin (src/marcas.py: Arno, Shark Ninja, VX Case): a arte inteira vai para dentro de uma moldura
  na cor da marca, com a faixa "LOJA OFICIAL <MARCA>" no topo e o selo dourado de verificado. Destaca do resto do
  feed e vale para post, slide do carrossel, Reels, story (feito da arte do post) e Telegram.

Logo das marcas: só o oficial, o do perfil de cada marca na Awin (assets/marcas/), sem mudar cor nem proporção, numa
plaquinha com o fundo original dele. Os termos dos programas (lidos em 27/10/2026) só proíbem anúncio pago em buscador
com o nome da marca. Marca sem logo cadastrado sai com o nome escrito.
"""
from PIL import Image, ImageDraw, ImageFont

from . import config, marcas

DOURADO = "#E2BE68"
BRANCO = "#FFFFFF"


def _fonte(tam, peso="Black"):
    if config.PERFIL == "ana":
        from . import layout_ana
        return layout_ana.sans(tam, peso)
    f = ImageFont.truetype(str(config.FONTE), tam)
    try:
        f.set_variation_by_name(peso)
    except Exception:
        pass
    return f


def _escurecer(cor, k=0.55):
    c = cor.lstrip("#")
    return tuple(int(int(c[i:i + 2], 16) * k) for i in (0, 2, 4))


# ------------------------------------------------------------------ ícones dos selos
def sacola(d, cx, cy, r, cor):
    """Sacolinha de compras (Shopee): corpo com alça."""
    lw = max(2, int(r * 0.2))
    d.rounded_rectangle([cx - r * 0.85, cy - r * 0.35, cx + r * 0.85, cy + r], max(2, int(r * 0.2)), fill=cor)
    d.arc([cx - r * 0.45, cy - r, cx + r * 0.45, cy + r * 0.1], 180, 360, fill=cor, width=lw)


def verificado(d, cx, cy, r, fundo, cor):
    """Selo de verificado: roseta dentada com um "certo" no meio (marca oficial)."""
    import math
    pts = []
    for i in range(24):
        ang = 2 * math.pi * i / 24
        rr = r if i % 2 == 0 else r * 0.84
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=fundo)
    lw = max(3, int(r * 0.22))
    d.line([(cx - r * 0.42, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.34), (cx + r * 0.45, cy - r * 0.3)],
           fill=cor, width=lw, joint="curve")


# ------------------------------------------------------------------ moldura das marcas oficiais
def oficial(oferta):
    return marcas.eh_marca(oferta)


def moldura_oficial(img, oferta):
    """Põe a arte (post 1080x1350, story/Reels 1080x1920) dentro da moldura da marca oficial e devolve a nova
    imagem, do mesmo tamanho. Oferta que não é de marca oficial volta como veio."""
    if not oficial(oferta):
        return img
    info = marcas.MARCAS[oferta["plataforma"]]
    cor, ana = info["cor"], config.PERFIL == "ana"
    L, A = img.size
    topo, lado = int(L * 0.105), int(L * 0.03)
    # a arte encolhe sem deformar e fica centralizada embaixo da faixa
    esc = min((L - 2 * lado) / L, (A - topo - lado) / A)
    w, h = int(L * esc), int(A * esc)
    arte = img.convert("RGB").resize((w, h), Image.LANCZOS)
    novo = Image.new("RGB", (L, A), cor)
    d = ImageDraw.Draw(novo)
    x0, y0 = (L - w) // 2, topo + (A - topo - lado - h) // 2
    raio = int(L * (0.04 if ana else 0.022))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], raio, fill=255)
    fino = max(3, int(L * 0.004))
    d.rounded_rectangle([x0 - fino - 3, y0 - fino - 3, x0 + w + fino + 2, y0 + h + fino + 2], raio + fino + 3,
                        outline=DOURADO, width=fino)
    novo.paste(arte, (x0, y0), m)

    # faixa do topo: selo de verificado + "LOJA OFICIAL" + nome da marca
    rs = int(topo * 0.36)
    f1 = _fonte(int(topo * 0.25), "Bold" if ana else "ExtraBold")
    f2 = _fonte(int(topo * 0.42), "Black")
    t1 = "loja oficial" if ana else "LOJA OFICIAL"
    t2 = info["nome"] if ana else info["nome"].upper()
    gap = int(L * 0.02)
    logo = _logo(info, int(topo * 0.5))
    if logo:   # plaquinha com o fundo original do logo
        pad = int(topo * 0.13)
        w2 = logo.width + 2 * pad
    else:
        w2 = d.textlength(t2, font=f2)
    total = 2 * rs + gap + d.textlength(t1, font=f1) + gap + w2
    x = (L - total) / 2
    cy = topo / 2 + int(L * 0.004)
    verificado(d, x + rs, cy, rs, DOURADO, cor)
    x += 2 * rs + gap
    d.text((x, cy), t1, font=f1, fill=DOURADO, anchor="lm")
    x += d.textlength(t1, font=f1) + gap
    if logo:
        hp = logo.height + 2 * pad
        y0p = int(cy - hp / 2)
        d.rounded_rectangle([x, y0p, x + w2, y0p + hp], hp // 4, fill=info.get("logo_fundo", BRANCO),
                            outline=DOURADO, width=max(2, fino - 1))
        novo.paste(logo, (int(x + pad), y0p + pad))
    else:
        d.text((x, cy), t2, font=f2, fill=BRANCO, anchor="lm")
    return novo


def _logo(info, altura):
    """Logo oficial da marca (assets/marcas/<arquivo>) na altura pedida, ou None."""
    arq = info.get("logo")
    caminho = config.RAIZ / "assets" / "marcas" / arq if arq else None
    if not caminho or not caminho.exists():
        return None
    img = Image.open(caminho).convert("RGB")
    return img.resize((max(1, round(img.width * altura / img.height)), altura), Image.LANCZOS)


# ------------------------------------------------------------------ selo em pílula (Garimpo)
def nome_e_cor(oferta):
    p = oferta.get("plataforma") or "shopee"
    if p in marcas.MARCAS:
        return marcas.MARCAS[p]["nome"].upper(), marcas.MARCAS[p]["cor"]
    return {"shopee": ("SHOPEE", "#EE4D2D"), "aliexpress": ("ALIEXPRESS", "#E43225")}.get(p, (p.upper(), "#24150A"))


def icone(d, oferta, cx, cy, r, cor):
    """Ícone da loja dentro do selo: sacola (Shopee), globo (AliExpress), verificado (marca oficial)."""
    p = oferta.get("plataforma") or "shopee"
    if p in marcas.MARCAS:
        verificado(d, cx, cy, r * 1.15, DOURADO, _escurecer(marcas.MARCAS[p]["cor"], 1.0))
    elif p == "aliexpress":
        from .imagem import globo
        globo(d, cx, cy, r, cor)
    else:
        sacola(d, cx, cy, r, cor)
