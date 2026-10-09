"""Monta a arte do post (1080x1350, formato retrato do feed) com foto, preço e selo."""
import io

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config

L, A = 1080, 1350
# Paleta da conta (config.PERFIS): no Garimpo VIP é a do logo (marrom e dourado)
FUNDO = config.CORES["fundo"]
ESCURO = config.CORES["escuro"]
DOURADO = config.CORES["destaque"]          # cor de destaque (dourado no Garimpo, rosa na Ana)
DOURADO_CLARO = config.CORES["destaque_claro"]
LARANJA = config.CORES["preco"]             # cor do preço
CINZA = config.CORES["cinza"]
SOMBRA = config.CORES["sombra"]
BRANCO = "#FFFFFF"


def _fonte(tam, peso="Bold"):
    f = ImageFont.truetype(str(config.FONTE), tam)
    try:
        f.set_variation_by_name(peso)
    except Exception:
        pass
    return f


def _baixar_foto(url):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _quebrar(draw, texto, fonte, largura, max_linhas=2):
    linhas, atual = [], ""
    for p in texto.split():
        teste = f"{atual} {p}".strip()
        if draw.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        while draw.textlength(linhas[-1] + "…", font=fonte) > largura and " " in linhas[-1]:
            linhas[-1] = linhas[-1].rsplit(" ", 1)[0]
        linhas[-1] += "…"
    return linhas


def _estrela(d, cx, cy, r, cor):
    import math
    pts = []
    for i in range(10):
        ang = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy - rr * math.sin(ang)))
    d.polygon(pts, fill=cor)


# Lojas (plataformas) e a cor do selo de cada uma
LOJAS = {
    "shopee": {"nome": "SHOPEE", "cor": "#EE4D2D"},
    "aliexpress": {"nome": "ALIEXPRESS", "cor": "#E43225"},
}


def plataforma(oferta):
    return oferta.get("plataforma") or "shopee"


def selo_loja(d, oferta, x, y, escala=1.0):
    """Selo "OFERTA <LOJA>" em pílula, com canto superior esquerdo em (x, y)."""
    info = LOJAS.get(plataforma(oferta), {"nome": plataforma(oferta).upper(), "cor": "#24150A"})
    f1, f2 = _fonte(int(26 * escala), "SemiBold"), _fonte(int(34 * escala), "Black")
    t1, t2 = "OFERTA ", info["nome"]
    w = d.textlength(t1, font=f1) + d.textlength(t2, font=f2)
    px, h = int(26 * escala), int(64 * escala)
    d.rounded_rectangle([x, y, x + w + 2 * px, y + h], h // 2, fill=info["cor"])
    d.text((x + px, y + (h - 26 * escala) / 2 - 3 * escala), t1, font=f1, fill="#FFFFFF")
    d.text((x + px + d.textlength(t1, font=f1), y + (h - 34 * escala) / 2 - 5 * escala), t2,
           font=f2, fill="#FFFFFF")
    return w + 2 * px


ACHADO_COR = "#0E7C86"        # azul-turquesa "diamante": não existe em nenhum outro selo da página
ACHADO_CLARO = "#7FE7EE"


def eh_achado(oferta):
    return oferta.get("nivel") == "achado"


def _diamante(d, cx, cy, r, cor, brilho):
    """Pedra lapidada: topo reto, ponta embaixo, com facetas."""
    topo, meio, ponta = cy - r * 0.62, cy - r * 0.18, cy + r * 0.85
    d.polygon([(cx - r * 0.55, topo), (cx + r * 0.55, topo), (cx + r, meio), (cx, ponta), (cx - r, meio)], fill=cor)
    d.polygon([(cx - r * 0.55, topo), (cx - r * 0.15, topo), (cx - r * 0.35, meio), (cx - r, meio)], fill=brilho)
    d.line([(cx - r, meio), (cx + r, meio)], fill=brilho, width=max(2, int(r * 0.08)))
    d.line([(cx - r * 0.35, meio), (cx, ponta), (cx + r * 0.35, meio)], fill=brilho, width=max(2, int(r * 0.07)))


def selo_achado(d, x, y, escala=1.0):
    """Faixa "💎 ACHADO ESCONDIDO" (pílula turquesa com diamante), canto superior esquerdo em (x, y)."""
    f1, f2 = _fonte(int(34 * escala), "Black"), _fonte(int(22 * escala), "SemiBold")
    t1, t2 = "ACHADO ESCONDIDO", "POUCA GENTE CONHECE"
    h = int(92 * escala)
    ic = int(30 * escala)
    px = int(24 * escala)
    w = 2 * ic + int(16 * escala) + max(d.textlength(t1, font=f1), d.textlength(t2, font=f2)) + 2 * px
    d.rounded_rectangle([x + 4, y + 6, x + w + 4, y + h + 6], h // 2, fill="#06484E")
    d.rounded_rectangle([x, y, x + w, y + h], h // 2, fill=ACHADO_COR, outline="#FFFFFF", width=max(3, int(4 * escala)))
    _diamante(d, x + px + ic, y + h / 2 + 2 * escala, ic, "#FFFFFF", ACHADO_CLARO)
    tx = x + px + 2 * ic + int(16 * escala)
    d.text((tx, y + int(12 * escala)), t1, font=f1, fill="#FFFFFF")
    d.text((tx, y + int(54 * escala)), t2, font=f2, fill=ACHADO_CLARO)
    return w


def moldura_achado(d, caixa, raio, escala=1.0):
    """Contorno turquesa no cartão da foto — o post de achado se destaca no feed."""
    x0, y0, x1, y1 = caixa
    e = int(10 * escala)
    d.rounded_rectangle([x0 - e, y0 - e, x1 + e, y1 + e], raio + e, outline=ACHADO_COR, width=e)


def _brl(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar(oferta: dict, destino, foto: Image.Image = None):
    if config.PERFIL == "ana":   # a Ana tem visual próprio (src/layout_ana.py)
        from . import layout_ana
        if foto is None:
            try:
                foto = _baixar_foto(oferta["imagem"])
            except Exception as e:
                print(f"⚠️  Não baixei a foto ({e}); usando arte sem foto.")
        return layout_ana.gerar_foto(oferta, destino, foto)
    img = Image.new("RGB", (L, A), FUNDO)
    d = ImageDraw.Draw(img)

    # Logo no topo (PNG com fundo transparente)
    try:
        logo = Image.open(config.LOGO).convert("RGBA")
        logo = ImageOps.contain(logo, (300, 165), Image.LANCZOS)
        img.paste(logo, ((L - logo.width) // 2, 20), logo)
    except Exception as e:
        print(f"⚠️  Logo não encontrado ({e}); usando a marca em texto.")
        f_marca = _fonte(56, "Black")
        d.text(((L - d.textlength(config.MARCA, font=f_marca)) / 2, 70), config.MARCA,
               font=f_marca, fill=ESCURO)

    # Foto do produto num cartão branco
    cx0, cy0, cx1, cy1 = 90, 205, L - 90, 205 + 715
    d.rounded_rectangle([cx0 + 6, cy0 + 10, cx1 + 6, cy1 + 10], 40, fill=SOMBRA)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], 40, fill=BRANCO)
    if foto is None:
        try:
            foto = _baixar_foto(oferta["imagem"])
        except Exception as e:
            print(f"⚠️  Não baixei a foto ({e}); usando arte sem foto.")
    if foto is not None:
        foto = ImageOps.contain(foto, (cx1 - cx0 - 80, cy1 - cy0 - 80), Image.LANCZOS)
        img.paste(foto, (cx0 + (cx1 - cx0 - foto.width) // 2, cy0 + (cy1 - cy0 - foto.height) // 2))
    else:
        f = _fonte(60, "Bold")
        t = "Oferta Shopee"
        d.text(((L - d.textlength(t, font=f)) / 2, (cy0 + cy1) / 2 - 30), t, font=f, fill=CINZA)

    # Selo da loja (canto superior esquerdo do cartão)
    selo_loja(d, oferta, cx0 + 28, cy0 + 28)
    if eh_achado(oferta):   # 💎 achado escondido: moldura turquesa + faixa no pé da foto
        moldura_achado(d, (cx0, cy0, cx1, cy1), 40)
        selo_achado(d, cx0 + 28, cy1 - 28 - 92)

    # Selo de desconto
    if oferta.get("desconto"):
        r = 105
        sx, sy = cx1 - 40, cy0 + 40
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=DOURADO, outline=BRANCO, width=8)
        f1, f2 = _fonte(64, "Black"), _fonte(34, "Bold")
        t1, t2 = f"-{oferta['desconto']}%", "OFF"
        d.text((sx - d.textlength(t1, font=f1) / 2, sy - 55), t1, font=f1, fill=BRANCO)
        d.text((sx - d.textlength(t2, font=f2) / 2, sy + 18), t2, font=f2, fill=BRANCO)

    # Título
    y = cy1 + 40
    f_tit = _fonte(50, "ExtraBold")
    for linha in _quebrar(d, oferta["titulo"], f_tit, L - 180, max_linhas=1):
        d.text((90, y), linha, font=f_tit, fill=ESCURO)
        y += 62

    # Preço (de / por) e avaliação
    y += 6
    f_de, f_rs, f_preco = _fonte(36, "Medium"), _fonte(44, "Bold"), _fonte(104, "Black")
    x = 90
    if oferta.get("preco_de"):
        de = f"R$ {_brl(oferta['preco_de'])}"
        d.text((x, y + 34), de, font=f_de, fill=CINZA)
        w = d.textlength(de, font=f_de)
        d.line([x - 4, y + 56, x + w + 4, y + 56], fill=CINZA, width=4)
        x += w + 26
    d.text((x, y + 30), "R$", font=f_rs, fill=DOURADO)
    x += d.textlength("R$", font=f_rs) + 10
    d.text((x, y - 18), oferta["preco_fmt"], font=f_preco, fill=LARANJA)

    f_info = _fonte(34, "SemiBold")
    vendas = f"{oferta['vendas']:,}".replace(",", ".")
    nota = (f"{oferta['avaliacao_pct']:.0f}% aprovação" if oferta.get("avaliacao_pct")
                else f"{oferta['nota']:.1f}".replace(".", ","))
    info = f"{nota}   •   {vendas}+ vendidos"
    yi = y + 140
    xi = 90 + 44
    _estrela(d, 90 + 18, yi + 21, 20, DOURADO)
    d.text((xi, yi), info, font=f_info, fill=CINZA)

    # Faixa de chamada
    d.rectangle([0, A - 100, L, A], fill=ESCURO)
    f_cta = _fonte(42, "ExtraBold")
    partes = [("COMENTE ", BRANCO), ("EU QUERO", DOURADO_CLARO), (" E RECEBA O LINK", BRANCO)]
    x = (L - sum(d.textlength(t, font=f_cta) for t, _ in partes)) / 2
    for t, cor in partes:
        d.text((x, A - 76), t, font=f_cta, fill=cor)
        x += d.textlength(t, font=f_cta)

    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino
