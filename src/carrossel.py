"""Carrossel do feed (1080x1350): capa (a própria arte do post) + foto grande + "por que vale a pena".

Cada conta usa o seu visual: o Garimpo VIP a paleta marrom e dourado (src/imagem.py) e a Ana o
visual leve dela (src/layout_ana.py). Só usa dados da oferta (nota, vendas, preço), nada inventado.
"""
from PIL import Image, ImageDraw, ImageOps

from . import config, imagem

L, A = 1080, 1350


def gerar(oferta, destino_capa, foto=None):
    """Gera os 3 slides; a capa vai em destino_capa e os outros ao lado (-2.jpg, -3.jpg).
    Devolve a lista de arquivos, na ordem do carrossel."""
    if foto is None:
        foto = imagem._baixar_foto(oferta["imagem"])
    imagem.gerar(oferta, destino_capa, foto=foto)
    base = str(destino_capa)[: -len(".jpg")]
    s2, s3 = f"{base}-2.jpg", f"{base}-3.jpg"
    if config.PERFIL == "ana":
        _foto_ana(oferta, foto, s2)
        _vale_ana(oferta, s3)
    else:
        _foto_garimpo(oferta, foto, s2)
        _vale_garimpo(oferta, s3)
    return [str(destino_capa), s2, s3]


def _motivos(oferta):
    nota = (f"{oferta['avaliacao_pct']:.0f}% de avaliações positivas" if oferta.get("avaliacao_pct")
            else f"Nota {oferta['nota']:.1f} de 5 nas avaliações".replace(".", ",", 1))
    vendas = f"{oferta['vendas']:,}".replace(",", ".")
    if oferta.get("preco_de") and oferta.get("desconto"):
        preco = f"De R$ {imagem._brl(oferta['preco_de'])} por R$ {oferta['preco_fmt']}"
    else:
        preco = f"Sai por R$ {oferta['preco_fmt']}"
    return [nota, f"Mais de {vendas} vendidos", preco]


def _check(d, cx, cy, r, fundo, traco):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fundo)
    d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)],
           fill=traco, width=max(4, int(r * 0.22)), joint="curve")


def _seta(d, x, cy, cor, tam=22):
    """Setinha "arrasta pro lado" (desenhada: nem toda fonte tem o caractere)."""
    d.line([(x, cy), (x + tam * 2, cy)], fill=cor, width=5)
    d.line([(x + tam * 2 - tam * 0.7, cy - tam * 0.7), (x + tam * 2, cy), (x + tam * 2 - tam * 0.7, cy + tam * 0.7)],
           fill=cor, width=5, joint="curve")


def _rodape_arrasta(d, fonte, cor, y):
    t = "arrasta para o lado"
    w = d.textlength(t, font=fonte) + 70
    x = (L - w) / 2
    d.text((x, y), t, font=fonte, fill=cor)
    _seta(d, x + w - 50, y + fonte.size * 0.62, cor)


# ---------------------------------------------------------------- Garimpo VIP
def _foto_garimpo(oferta, foto, destino):
    img = Image.new("RGB", (L, A), imagem.FUNDO)
    d = ImageDraw.Draw(img)
    cx0, cy0, cx1, cy1 = 60, 60, L - 60, 1060
    d.rounded_rectangle([cx0 + 6, cy0 + 10, cx1 + 6, cy1 + 10], 44, fill=imagem.SOMBRA)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], 44, fill=imagem.BRANCO)
    f = ImageOps.contain(foto, (cx1 - cx0 - 60, cy1 - cy0 - 60), Image.LANCZOS)
    img.paste(f, (cx0 + (cx1 - cx0 - f.width) // 2, cy0 + (cy1 - cy0 - f.height) // 2))
    imagem.selo_loja(d, oferta, cx0 + 28, cy0 + 28)
    y = cy1 + 45
    f_tit = imagem._fonte(46, "ExtraBold")
    for linha in imagem._quebrar(d, oferta["titulo"], f_tit, L - 160, max_linhas=2):
        d.text(((L - d.textlength(linha, font=f_tit)) / 2, y), linha, font=f_tit, fill=imagem.ESCURO)
        y += 58
    _rodape_arrasta(d, imagem._fonte(34, "SemiBold"), imagem.DOURADO, A - 90)
    img.save(destino, "JPEG", quality=90, optimize=True)


def _vale_garimpo(oferta, destino):
    img = Image.new("RGB", (L, A), imagem.FUNDO)
    d = ImageDraw.Draw(img)
    try:
        logo = ImageOps.contain(Image.open(config.LOGO).convert("RGBA"), (300, 165), Image.LANCZOS)
        img.paste(logo, ((L - logo.width) // 2, 40), logo)
    except Exception:
        pass
    f_h = imagem._fonte(72, "Black")
    t = "POR QUE É UM ACHADO"
    d.text(((L - d.textlength(t, font=f_h)) / 2, 270), t, font=f_h, fill=imagem.ESCURO)
    d.rectangle([(L - 160) / 2, 370, (L + 160) / 2, 378], fill=imagem.DOURADO)
    f_m = imagem._fonte(46, "Bold")
    y = 460
    for m in _motivos(oferta):
        d.rounded_rectangle([90, y - 30, L - 90, y + 110], 36, fill=imagem.BRANCO)
        _check(d, 160, y + 40, 38, imagem.DOURADO, imagem.BRANCO)
        linhas = imagem._quebrar(d, m, f_m, L - 330, max_linhas=2)
        ty = y + 40 - len(linhas) * 29
        for linha in linhas:
            d.text((230, ty), linha, font=f_m, fill=imagem.ESCURO)
            ty += 58
        y += 180
    f_s = imagem._fonte(36, "SemiBold")
    t = "Salva pra não perder e manda pra quem precisa!"
    d.text(((L - d.textlength(t, font=f_s)) / 2, y + 20), t, font=f_s, fill=imagem.CINZA)
    # mesma faixa de chamada da capa
    d.rectangle([0, A - 150, L, A], fill=imagem.ESCURO)
    f_cta = imagem._fonte(48, "ExtraBold")
    partes = [("COMENTE ", imagem.BRANCO), ("EU QUERO", imagem.DOURADO_CLARO), (" E RECEBA O LINK", imagem.BRANCO)]
    x = (L - sum(d.textlength(t, font=f_cta) for t, _ in partes)) / 2
    for t, cor in partes:
        d.text((x, A - 104), t, font=f_cta, fill=cor)
        x += d.textlength(t, font=f_cta)
    img.save(destino, "JPEG", quality=90, optimize=True)


# ---------------------------------------------------------------- Ana Novo Achados
def _foto_ana(oferta, foto, destino):
    from . import layout_ana as la
    img = la.degrade(L, A)
    caixa = (110, 90, L - 110, 1080)
    la.colar_foto_no_arco(img, foto, caixa)
    d = ImageDraw.Draw(img)
    la.selo_loja(d, oferta, caixa[0] + 30, caixa[3] - 80)
    y = 1110
    f_tit = la.serif(58)
    for linha in la.quebrar(d, oferta["titulo"], f_tit, L - 180, max_linhas=2):
        d.text(((L - d.textlength(linha, font=f_tit)) / 2, y), linha, font=f_tit, fill=la.TEXTO)
        y += 68
    _rodape_arrasta(d, la.sans(32, "Medium"), la.ROSA_ESCURA, A - 80)
    img.save(destino, "JPEG", quality=90, optimize=True)


def _vale_ana(oferta, destino):
    from . import layout_ana as la
    img = la.degrade(L, A)
    av = la.avatar(170)
    if av:
        img.paste(av, ((L - av.width) // 2, 60), av)
    d = ImageDraw.Draw(img)
    f_h = la.serif(84)
    t = "por que vale a pena"
    d.text(((L - d.textlength(t, font=f_h)) / 2, 280), t, font=f_h, fill=la.TEXTO)
    f_m = la.sans(44, "Medium")
    y = 480
    for m in _motivos(oferta):
        d.rounded_rectangle([90, y - 30, L - 90, y + 110], 55, fill=la.BRANCO, outline=la.ROSA, width=3)
        _check(d, 165, y + 40, 36, la.ROSA, la.TEXTO)
        linhas = la.quebrar(d, m, f_m, L - 330, max_linhas=2)
        ty = y + 40 - len(linhas) * 28
        for linha in linhas:
            d.text((230, ty), linha, font=f_m, fill=la.TEXTO)
            ty += 56
        y += 180
    f_s = la.sans(34, "Medium")
    t = "salva pra não perder e manda pra uma amiga"
    d.text(((L - d.textlength(t, font=f_s)) / 2, y + 20), t, font=f_s, fill=la.CINZA)
    la.botao_cta(img, A - 110, L, escala=1.1)
    img.save(destino, "JPEG", quality=90, optimize=True)
