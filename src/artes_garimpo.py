"""Modelos extras da arte do Garimpo VIP (1080x1350), em rodízio com o clássico de src/imagem.py.

Mesma paleta (marrom e dourado) e mesma fonte (Montserrat), mas com cara diferente no feed:
- "noite": fundo marrom escuro, foto em cartão creme com borda dourada, preço dourado gigante.
- "manchete": o preço vira a manchete no topo (gancho), foto grande e faixa dourada embaixo.
"""
from PIL import Image, ImageDraw, ImageOps

from . import config, imagem

L, A = 1080, 1350
MARROM = imagem.ESCURO              # #24150A
DOURADO = imagem.DOURADO            # #A07E30
DOURADO_CLARO = imagem.DOURADO_CLARO
CREME = "#F6EEDF"
CREME_ESCURO = "#C9B89A"
BRANCO = "#FFFFFF"
f = imagem._fonte


def _logo(largura, claro=False):
    """Logo do Garimpo; claro=True pinta as letras marrons de creme (para fundo escuro)."""
    lg = Image.open(config.LOGO).convert("RGBA")
    if claro:
        px = lg.load()
        for y in range(lg.height):
            for x in range(lg.width):
                r, g, b, a = px[x, y]
                if a and (r + g + b) / 3 < 110:      # partes marrons viram creme; o dourado fica
                    px[x, y] = (0xF6, 0xEE, 0xDF, a)
    return ImageOps.contain(lg, (largura, largura), Image.LANCZOS)


def _info(oferta):
    nota = (f"{oferta['avaliacao_pct']:.0f}% avaliações positivas" if oferta.get("avaliacao_pct")
            else f"nota {oferta['nota']:.1f}".replace(".", ","))
    return f"{nota}   •   " + f"{oferta['vendas']:,}+ vendidos".replace(",", ".")


def _centro(d, y, texto, fonte, cor):
    d.text(((L - d.textlength(texto, font=fonte)) / 2, y), texto, font=fonte, fill=cor)


def _foto_no(img, foto, caixa, margem=50):
    x0, y0, x1, y1 = caixa
    if foto is None:
        return
    ft = ImageOps.contain(foto, (x1 - x0 - 2 * margem, y1 - y0 - 2 * margem), Image.LANCZOS)
    img.paste(ft, (x0 + (x1 - x0 - ft.width) // 2, y0 + (y1 - y0 - ft.height) // 2))


def _cta(d, y, h, fundo, cor_texto, cor_quero):
    d.rectangle([0, y, L, y + h], fill=fundo)
    fc = f(42, "ExtraBold")
    partes = [("COMENTE ", cor_texto), ("EU QUERO", cor_quero), (" E RECEBA O LINK", cor_texto)]
    x = (L - sum(d.textlength(t, font=fc) for t, _ in partes)) / 2
    for t, cor in partes:
        d.text((x, y + (h - 42) / 2 - 6), t, font=fc, fill=cor)
        x += d.textlength(t, font=fc)


# ---------------------------------------------------------------- modelo "noite"
def noite(oferta, destino, foto=None):
    img = Image.new("RGB", (L, A), MARROM)
    d = ImageDraw.Draw(img)
    # brilho sutil atrás da foto
    for i in range(14, 0, -1):
        k = i / 14
        cor = tuple(int(c1 + (c2 - c1) * (1 - k) * 0.35) for c1, c2 in zip((0x24, 0x15, 0x0A), (0xA0, 0x7E, 0x30)))
        d.ellipse([L / 2 - 520 * k, 560 - 420 * k, L / 2 + 520 * k, 560 + 420 * k], fill=cor)
    lg = _logo(150, claro=True)
    img.paste(lg, (70, 28), lg)
    ft = f(30, "Bold")
    t = "ACHADO VIP DO DIA"
    d.text((L - 70 - d.textlength(t, font=ft), 96), t, font=ft, fill=DOURADO_CLARO)
    d.line([L - 70 - d.textlength(t, font=ft), 140, L - 70, 140], fill=DOURADO, width=3)

    caixa = (120, 210, L - 120, 210 + 640)
    d.rounded_rectangle([caixa[0] - 10, caixa[1] - 10, caixa[2] + 10, caixa[3] + 10], 46, fill=DOURADO)
    d.rounded_rectangle(caixa, 38, fill=BRANCO)
    _foto_no(img, foto, caixa)
    imagem.selo_loja(d, oferta, caixa[0] + 26, caixa[1] + 26, escala=0.9)
    if imagem.eh_achado(oferta):
        imagem.selo_achado(d, caixa[0] + 26, caixa[3] - 26 - 92)
    if oferta.get("desconto"):   # fita dourada no canto
        fita = Image.new("RGBA", (420, 90), (0, 0, 0, 0))
        dd = ImageDraw.Draw(fita)
        dd.rectangle([0, 0, 420, 90], fill=DOURADO_CLARO)
        fd = f(46, "Black")
        td = f"-{oferta['desconto']}% OFF"
        dd.text(((420 - dd.textlength(td, font=fd)) / 2, 14), td, font=fd, fill=MARROM)
        fita = fita.rotate(-35, expand=True, resample=Image.BICUBIC)
        img.paste(fita, (caixa[2] - fita.width + 95, caixa[1] - 70), fita)
        d = ImageDraw.Draw(img)

    y = caixa[3] + 44
    ftit = f(46, "Bold")
    for linha in imagem._quebrar(d, oferta["titulo"], ftit, L - 180, max_linhas=1):
        _centro(d, y, linha, ftit, CREME)
        y += 60
    y += 4
    fp, frs = f(124, "Black"), f(48, "Bold")
    preco = oferta["preco_fmt"]
    wtot = d.textlength("R$ ", font=frs) + d.textlength(preco, font=fp)
    x = (L - wtot) / 2
    d.text((x, y + 52), "R$ ", font=frs, fill=DOURADO_CLARO)
    d.text((x + d.textlength("R$ ", font=frs), y - 6), preco, font=fp, fill=DOURADO_CLARO)
    y += 150
    fi = f(32, "SemiBold")
    linha = _info(oferta)
    if oferta.get("preco_de"):
        linha = f"antes R$ {imagem._brl(oferta['preco_de'])}   •   " + linha
    _centro(d, y, linha, fi, CREME_ESCURO)
    _cta(d, A - 100, 100, DOURADO, MARROM, BRANCO)
    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino


# ---------------------------------------------------------------- modelo "manchete"
def manchete(oferta, destino, foto=None):
    img = Image.new("RGB", (L, A), imagem.FUNDO)
    d = ImageDraw.Draw(img)
    lg = _logo(120)
    img.paste(lg, (60, 26), lg)
    imagem.selo_loja(d, oferta, L - 60 - 300, 52, escala=0.85)

    # manchete: o preço é o gancho
    fs = f(40, "Bold")
    pre = f"DE R$ {imagem._brl(oferta['preco_de'])} POR APENAS" if oferta.get("preco_de") else "SAI POR APENAS"
    _centro(d, 170, pre, fs, imagem.CINZA)
    if oferta.get("preco_de"):
        w = d.textlength(f"DE R$ {imagem._brl(oferta['preco_de'])}", font=fs)
        x0 = (L - d.textlength(pre, font=fs)) / 2
        d.line([x0 - 4, 196, x0 + w + 4, 196], fill=imagem.CINZA, width=4)
    fp, frs = f(170, "Black"), f(64, "Bold")
    preco = oferta["preco_fmt"]
    wtot = d.textlength("R$", font=frs) + 14 + d.textlength(preco, font=fp)
    x = (L - wtot) / 2
    d.text((x, 290), "R$", font=frs, fill=DOURADO)
    d.text((x + d.textlength("R$", font=frs) + 14, 200), preco, font=fp, fill=MARROM)
    d.rectangle([(L - 200) / 2, 418, (L + 200) / 2, 426], fill=DOURADO)

    # foto em painel branco de ponta a ponta
    caixa = (0, 460, L, 1110)
    d.rectangle(caixa, fill=BRANCO)
    _foto_no(img, foto, caixa, margem=36)
    if imagem.eh_achado(oferta):
        imagem.selo_achado(d, 40, caixa[3] - 30 - 92)
    if oferta.get("desconto"):   # etiqueta pendurada no canto
        cx, top = L - 150, caixa[1]
        d.line([cx, top, cx, top + 40], fill=MARROM, width=4)
        d.polygon([(cx - 80, top + 80), (cx, top + 36), (cx + 80, top + 80), (cx + 80, top + 250), (cx - 80, top + 250)],
                  fill=MARROM)
        d.ellipse([cx - 11, top + 58, cx + 11, top + 80], fill=BRANCO)
        f1, f2 = f(58, "Black"), f(34, "Bold")
        t1, t2 = f"-{oferta['desconto']}%", "OFF"
        d.text((cx - d.textlength(t1, font=f1) / 2, top + 110), t1, font=f1, fill=DOURADO_CLARO)
        d.text((cx - d.textlength(t2, font=f2) / 2, top + 182), t2, font=f2, fill=BRANCO)

    y = caixa[3] + 28
    ftit = f(44, "ExtraBold")
    for linha in imagem._quebrar(d, oferta["titulo"], ftit, L - 140, max_linhas=1):
        _centro(d, y, linha, ftit, MARROM)
        y += 56
    fi = f(32, "SemiBold")
    _centro(d, y + 8, _info(oferta), fi, imagem.CINZA)
    _cta(d, A - 104, 104, MARROM, BRANCO, DOURADO_CLARO)
    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino
