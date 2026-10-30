"""Artes do carrossel de achados (src/achados.py): várias versões de cada slide, para os posts não ficarem todos
iguais no feed. A cada carrossel o robô usa uma versão diferente (o contador fica em data/<perfil>/achados.json).

Garimpo VIP — slide de produto: 0 = cartão do feed · 1 = "mina" (fundo escuro) · 2 = "ouro" (fundo dourado);
              slide final: 0 = saída da mina (laranja) · 1 = noite (azul) ; título do vídeo: 3 textos.
Ana         — slide de produto: 0 = arco · 1 = polaroid (lavanda) · 2 = círculo (menta);
              slide final: 3 paletas (rosa, lavanda, menta) e 3 textos; título do vídeo: 3 textos.
"""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import config, imagem, lojas_arte, marcas

L, A = 1080, 1350
NOMES_LOJA = {"shopee": "SHOPEE", "aliexpress": "ALIEXPRESS", **{p: m["nome"].upper() for p, m in marcas.MARCAS.items()}}

TITULOS_GARIMPO = [("ACHADOS DO ZÉ", "arrasta pro lado"), ("O ZÉ GARIMPOU", "arrasta e confere"),
                   ("OLHA O QUE O ZÉ ACHOU", "arrasta pro lado")]
TITULOS_ANA = [("achadinhos da Ana", "arrasta pro lado"), ("a Ana separou pra você", "arrasta e confere"),
               ("olha o que eu achei", "arrasta pro lado")]
FINAIS_GARIMPO = ["Gostou de algum?", "Qual é o seu favorito?", "Bateu o olho em algum?"]
FINAIS_ANA = ["gostou de algum?", "qual é o seu favorito?", "bateu o olho em algum?"]
N_PRODUTO, N_FINAL_GARIMPO, N_FINAL_ANA, N_TITULO = 3, 2, 3, 3


def _brl_linha(o):
    return f"R$ {o['preco_fmt']}"


def _info(o):
    if marcas.eh_marca(o):
        return marcas.texto_oficial(o)
    vendas = f"{o.get('vendas', 0):,}".replace(",", ".")
    if o.get("avaliacao_pct"):
        return f"{o['avaliacao_pct']:.0f}% aprovação  •  {vendas}+ vendidos"
    return f"nota {str(o.get('nota', '')).replace('.', ',')}  •  {vendas}+ vendidos"


def _loja(o):
    return NOMES_LOJA.get(o.get("plataforma") or "shopee", "SHOPEE")


def _loja_nome(o):
    """Nome da loja como se escreve: Shopee, AliExpress, Shark Ninja..."""
    return marcas.nome(o) if marcas.eh_marca(o) else {"ALIEXPRESS": "AliExpress"}.get(_loja(o), _loja(o).title())


def _degrade(topo, base):
    img = Image.new("RGB", (L, A))
    d = ImageDraw.Draw(img)
    for y in range(A):
        k = y / (A - 1)
        d.line([(0, y), (L, y)], fill=tuple(int(c1 + (c2 - c1) * k) for c1, c2 in zip(topo, base)))
    return img


def _centro(d, y, texto, fonte, cor, stroke=0, cor_stroke=(0, 0, 0)):
    d.text(((L - d.textlength(texto, font=fonte)) / 2, y), texto, font=fonte, fill=cor,
           stroke_width=stroke, stroke_fill=cor_stroke)


def _ajustar(d, texto, fabrica, tam, largura, minimo=44):
    """Fonte do maior tamanho (até `tam`) em que o texto cabe na largura."""
    while tam > minimo:
        f = fabrica(tam)
        if d.textlength(texto, font=f) <= largura:
            return f
        tam -= 4
    return fabrica(minimo)


def _barra_quero(d, pos, y):
    fc = imagem._fonte(46, "ExtraBold")
    partes = [("COMENTE ", imagem.BRANCO), (f"QUERO {pos}", imagem.DOURADO_CLARO), (" E RECEBA O LINK", imagem.BRANCO)]
    x = (L - sum(d.textlength(t, font=fc) for t, _ in partes)) / 2
    for t, cor in partes:
        d.text((x, y), t, font=fc, fill=cor)
        x += d.textlength(t, font=fc)


# ================================================================== GARIMPO VIP — produto
def produto_garimpo(v, oferta, foto, pos, destino):
    if v == 1:
        img = _mina(oferta, foto, pos)
    elif v == 2:
        img = _ouro(oferta, foto, pos)
    else:   # 0: o cartão do feed com o selo do número
        imagem.gerar(oferta, destino, foto=foto, moldura=False)
        img = Image.open(destino).convert("RGB")
        d = ImageDraw.Draw(img)
        _selo_numero(d, 74, 74, 56, imagem.DOURADO, imagem.ESCURO, imagem._fonte(76, "Black"), pos, imagem.ESCURO)
        d.rectangle([0, A - 118, L, A], fill=imagem.ESCURO)
        _barra_quero(d, pos, A - 84)
    img = lojas_arte.moldura_oficial(img, oferta)   # marca oficial da Awin: moldura da marca
    img.save(destino, "JPEG", quality=90, optimize=True)


# ================================================================== capa com produto (Garimpo VIP)
ZE_CAPA = {"aponta": config.RAIZ / "assets" / "ze" / "capa" / "ze_aponta.png",
           "joia": config.RAIZ / "assets" / "ze" / "capa" / "ze_joia.png"}


def capa_produto(oferta, foto, n_mais, pose, destino):
    """Capa do carrossel no lugar do vídeo de abertura (30/10/2026, sugestão do Gemini aprovada pelo Fred): o 1º
    produto grande num cartão branco, selo da loja e "+3 ACHADOS" no topo, faixa com nome/nota/preço e o Zé
    pequeno (recortado do ze_joinha.mp4) no canto de baixo. Vale como o slide do produto 1 ("QUERO 1")."""
    img = Image.new("RGB", (L, A), imagem.FUNDO)
    d = ImageDraw.Draw(img)
    cx0, cy0, cx1, cy1 = 44, 44, L - 44, 1000
    d.rounded_rectangle([cx0 + 6, cy0 + 10, cx1 + 6, cy1 + 10], 44, fill=imagem.SOMBRA)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], 44, fill=imagem.BRANCO)
    if foto is not None:
        f = ImageOps.contain(foto.convert("RGB"), (cx1 - cx0 - 60, cy1 - cy0 - 140), Image.LANCZOS)
        img.paste(f, (cx0 + (cx1 - cx0 - f.width) // 2, cy0 + 120 + (cy1 - cy0 - 150 - f.height) // 2))
    _selo_numero(d, cx0 + 66, cy0 + 62, 44, imagem.DOURADO, imagem.ESCURO, imagem._fonte(60, "Black"), 1,
                 imagem.ESCURO)
    fim_selo = cx0 + 126 + imagem.selo_loja(d, oferta, cx0 + 126, cy0 + 30)
    t = f"+{n_mais} ACHADOS  ›"
    f_a = imagem._fonte(30, "ExtraBold")
    w = d.textlength(t, font=f_a)
    if fim_selo + 20 < cx1 - w - 70:   # selo comprido (INTERNACIONAL) não deixa espaço: fica sem o "+3"
        d.rounded_rectangle([cx1 - w - 70, cy0 + 30, cx1 - 30, cy0 + 94], 32, fill=imagem.DOURADO)
        d.text((cx1 - w - 50, cy0 + 45), t, font=f_a, fill=imagem.BRANCO)
    # faixa de baixo: nome, nota/vendas (ou "Loja oficial X") e preço; o texto para antes do Zé
    d.rectangle([0, 1040, L, A], fill=imagem.ESCURO)
    x0, y = 60, 1062
    f_tit = imagem._fonte(50, "ExtraBold")
    for ln in imagem._quebrar(d, oferta["titulo"], f_tit, 640, max_linhas=2):
        d.text((x0, y), ln, font=f_tit, fill=imagem.BRANCO)
        y += 58
    y += 6
    f_info = imagem._fonte(32, "SemiBold")
    if marcas.eh_marca(oferta):
        d.text((x0, y), marcas.texto_oficial(oferta), font=f_info, fill=imagem.DOURADO_CLARO)
    else:
        imagem._estrela(d, x0 + 18, y + 21, 20, imagem.DOURADO_CLARO)
        d.text((x0 + 46, y), _info(oferta).removeprefix("nota "), font=f_info, fill=imagem.DOURADO_CLARO)
    d.text((x0, y + 50), _brl_linha(oferta), font=imagem._fonte(64, "Black"), fill=imagem.BRANCO)
    ze = Image.open(ZE_CAPA[pose]).convert("RGBA")
    alt = 340
    ze = ze.resize((int(ze.width * alt / ze.height), alt), Image.LANCZOS)
    zx, zy = L - ze.width - 40, A - alt
    sombra = ze.getchannel("A").point(lambda v: int(v * 0.45)).filter(ImageFilter.GaussianBlur(10))
    img.paste(Image.new("RGB", ze.size, (0, 0, 0)), (zx + 8, zy + 6), sombra)
    img.paste(ze, (zx, zy), ze)
    img = lojas_arte.moldura_oficial(img, oferta)   # marca oficial da Awin: moldura da marca
    img.save(destino, "JPEG", quality=90, optimize=True)


def _selo_numero(d, cx, cy, r, fundo, contorno, fonte, pos, cor):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fundo, outline=contorno, width=6)
    d.text((cx, cy + 2), str(pos), font=fonte, fill=cor, anchor="mm")


def _mina(o, foto, pos):
    from . import top
    f = top._f
    im = Image.new("RGB", (L, A))
    d = ImageDraw.Draw(im)
    for y in range(A):
        k = y / A
        d.line([(0, y), (L, y)], fill=(int(80 - 36 * k), int(38 - 18 * k), int(10 - 5 * k)))
    borda = (45, 20, 5)
    d.ellipse((50, 40, 190, 180), fill=top.AM)
    d.text((120, 112), str(pos), font=f(96), fill=borda, anchor="mm")
    d.text((220, 58), "ACHADO DO ZÉ", font=f(32), fill=top.AM)
    d.text((220, 98), f"oferta {_loja_nome(o)}", font=f(52), fill=top.BR)
    d.rounded_rectangle((60, 220, L - 60, 900), 36, fill=top.CARD)
    fo = foto.copy()
    fo.thumbnail((L - 180, 620), Image.LANCZOS)
    im.paste(fo, ((L - fo.width) // 2, 250 + (620 - fo.height) // 2))
    imagem.selo_loja(d, o, 90, 900 - 30 - 58, escala=0.9)   # selo da loja (com 🌎 internacional) no pé do cartão
    if o.get("desconto"):
        t = f"-{o['desconto']}%"
        ft = f(36)
        w = d.textlength(t, font=ft)
        d.rounded_rectangle((L - 90 - w - 40, 250, L - 90, 312), 30, fill=top.VERMELHO)
        d.text((L - 90 - w - 20, 258), t, font=ft, fill=top.BR)
    y = 930
    for ln in top._quebrar(d, o["titulo"], f(40), L - 140):
        top._ctext(d, y, ln, f(40), top.BR)
        y += 52
    variacoes = o.get("preco_max") and o["preco_max"] > o["preco"] * 1.02
    top._ctext(d, y + 12, "a partir de" if variacoes else "por", f(30), top.BEGE)
    top._ctext(d, y + 44, _brl_linha(o), f(80), top.AM, 4, borda)
    top._ctext(d, y + 150, _info(o), f(32), top.BR)
    t = f"Comenta  QUERO {pos}  que o Zé te manda o link"
    ft = f(34)
    w = d.textlength(t, font=ft)
    d.rounded_rectangle(((L - w) / 2 - 30, A - 112, (L + w) / 2 + 30, A - 44), 34, fill=top.VERDE)
    top._ctext(d, A - 104, t, ft, top.BR)
    return im


def _ouro(o, foto, pos):
    im = Image.new("RGB", (L, A), (226, 178, 54))
    d = ImageDraw.Draw(im)
    d.ellipse((-260, -260, 640, 640), fill=(238, 200, 98))
    d.ellipse((520, 760, 1380, 1620), fill=(212, 162, 38))
    d.ellipse((120, 150, 960, 990), fill=imagem.BRANCO)
    fo = ImageOps.contain(foto, (620, 620), Image.LANCZOS)
    im.paste(fo, (540 - fo.width // 2, 570 - fo.height // 2))
    _selo_numero(d, 100, 100, 62, imagem.ESCURO, imagem.BRANCO, imagem._fonte(78, "Black"), pos, (238, 200, 98))
    rascunho = ImageDraw.Draw(Image.new("RGB", (8, 8)))   # selo da loja (com 🌎 internacional) no canto
    imagem.selo_loja(d, o, L - 70 - imagem.selo_loja(rascunho, o, 0, 0), 62)
    if o.get("desconto"):
        cx, cy, r = 880, 920, 92
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(205, 48, 36), outline=imagem.BRANCO, width=6)
        d.text((cx, cy - 12), f"-{o['desconto']}%", font=imagem._fonte(50, "Black"), fill=imagem.BRANCO, anchor="mm")
        d.text((cx, cy + 34), "OFF", font=imagem._fonte(32, "ExtraBold"), fill=imagem.BRANCO, anchor="mm")
    y = 965
    ft = imagem._fonte(44, "ExtraBold")
    for ln in imagem._quebrar(d, o["titulo"], ft, L - 150, max_linhas=2):
        _centro(d, y, ln, ft, imagem.ESCURO)
        y += 54
    _centro(d, y + 6, _brl_linha(o), imagem._fonte(104, "Black"), imagem.ESCURO)
    _centro(d, y + 128, _info(o), imagem._fonte(32, "SemiBold"), (92, 58, 12))
    d.rectangle([0, A - 118, L, A], fill=imagem.ESCURO)
    _barra_quero(d, pos, A - 84)
    return im


# ================================================================== ANA — produto
def produto_ana(v, oferta, foto, pos, destino):
    from . import layout_ana as la
    if v == 1:
        img = _polaroid(oferta, foto, pos)
    elif v == 2:
        img = _circulo(oferta, foto, pos)
    else:   # 0: o arco do feed com o selo do número
        imagem.gerar(oferta, destino, foto=foto, moldura=False)
        img = Image.open(destino).convert("RGB")
        d = ImageDraw.Draw(img)
        cx, cy, r = L // 2, 66, 56
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=la.ROSA_ESCURA, outline=la.BRANCO, width=6)
        d.text((cx, cy + 2), str(pos), font=la.serif(78), fill=la.BRANCO, anchor="mm")
    img = lojas_arte.moldura_oficial(img, oferta)   # marca oficial da Awin: moldura da marca
    img.save(destino, "JPEG", quality=90, optimize=True)


def _numero_ana(img, cx, cy, pos, r=56):
    from . import layout_ana as la
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=la.ROSA_ESCURA, outline=la.BRANCO, width=6)
    d.text((cx, cy + 2), str(pos), font=la.serif(76), fill=la.BRANCO, anchor="mm")


def _polaroid(o, foto, pos):
    from . import layout_ana as la
    img = _degrade((252, 243, 250), (238, 224, 244))
    lp, ap = 820, 1000
    pol = Image.new("RGBA", (lp, ap), (0, 0, 0, 0))
    d = ImageDraw.Draw(pol)
    d.rounded_rectangle((0, 0, lp - 1, ap - 1), 22, fill=la.BRANCO)
    d.rectangle((46, 46, lp - 46, 46 + 728), fill=(250, 247, 249))
    fo = ImageOps.contain(foto, (700, 700), Image.LANCZOS)
    pol.paste(fo, (lp // 2 - fo.width // 2, 46 + 364 - fo.height // 2))
    la.selo_loja(d, o, 66, 46 + 728 - 70)   # "na Shopee", "na AliExpress · internacional"... no pé da foto
    ft = la.serif(46)
    y = 806
    for ln in la.quebrar(d, o["titulo"], ft, lp - 100, max_linhas=2):
        d.text(((lp - d.textlength(ln, font=ft)) / 2, y), ln, font=ft, fill=la.TEXTO)
        y += 54
    sombra = Image.new("RGBA", (lp + 120, ap + 120), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((60, 70, lp + 60, ap + 70), 22, fill=(90, 40, 80, 70))
    sombra = sombra.filter(ImageFilter.GaussianBlur(18))
    sombra.alpha_composite(pol, (60, 60))
    girada = sombra.rotate(-3, resample=Image.BICUBIC, expand=True)
    img.paste(girada, ((L - girada.width) // 2, 20), girada)
    if o.get("desconto"):
        la.adesivo(img, 880, 300, f"-{o['desconto']}%", "OFF", r=92, angulo=10)
    _numero_ana(img, 112, 112, pos)
    d = ImageDraw.Draw(img)
    fp = la.sans(70, "Black")
    t = _brl_linha(o)
    w = d.textlength(t, font=fp)
    d.rounded_rectangle(((L - w) / 2 - 60, 1060, (L + w) / 2 + 60, 1160), 50, fill=la.ROSA)
    d.text((L / 2, 1112), t, font=fp, fill=la.TEXTO, anchor="mm")
    _centro(d, 1180, _info(o), la.sans(30, "Medium"), la.CINZA)
    la.botao_cta(img, A - 80, L, escala=0.95)
    return img


def _circulo(o, foto, pos):
    from . import layout_ana as la
    img = _degrade((240, 250, 245), (212, 238, 224))
    d = ImageDraw.Draw(img)
    d.ellipse((140, 120, 940, 920), fill=la.BRANCO, outline=la.ROSA_ESCURA, width=8)
    fo = ImageOps.contain(foto, (620, 620), Image.LANCZOS)
    img.paste(fo, (540 - fo.width // 2, 520 - fo.height // 2))
    _numero_ana(img, 190, 190, pos)
    if o.get("desconto"):
        la.adesivo(img, 872, 240, f"-{o['desconto']}%", "OFF", r=92, angulo=10)
    d = ImageDraw.Draw(img)
    w = la.selo_loja(ImageDraw.Draw(Image.new("RGB", (8, 8))), o, 0, 0)   # selo da loja no canto, fora do círculo
    la.selo_loja(d, o, L - 40 - w, 40)
    ft = la.serif(56)
    y = 945
    for ln in la.quebrar(d, o["titulo"], ft, L - 150, max_linhas=2):
        d.text(((L - d.textlength(ln, font=ft)) / 2, y), ln, font=ft, fill=la.TEXTO)
        y += 62
    fp = la.sans(66, "Black")
    t = _brl_linha(o)
    w = d.textlength(t, font=fp)
    d.rounded_rectangle(((L - w) / 2 - 56, 1082, (L + w) / 2 + 56, 1176), 47, fill=la.TEXTO)
    d.text((L / 2, 1130), t, font=fp, fill=la.BRANCO, anchor="mm")
    _centro(d, 1192, _info(o), la.sans(30, "Medium"), la.CINZA)
    la.botao_cta(img, A - 62, L, escala=0.85)
    return img


# ================================================================== slides finais
def final_garimpo(v, n, n_variante, youtube=False):
    from . import top
    tipo = "semana" if v % N_FINAL_GARIMPO == 0 else "mes"   # laranja (saída da mina) ou azul (noite)
    tm = top.TEMAS[tipo]
    bg, img, m, ih = top._cena(tipo)
    im = Image.new("RGB", (L, A), tm["fundo"])
    im.paste(bg.crop((0, 0, L, A)), (0, 0))
    im.paste(img, (0, 0), m)
    d = ImageDraw.Draw(im)
    es = tm["borda"]
    top._ctext(d, 830, FINAIS_GARIMPO[n_variante % 3], top._f(66), top.AM, 5, es)
    fim = "que o Zé te responde aqui" if youtube else "que o Zé te manda o link no direct"
    for i, ln in enumerate([f"Comenta  QUERO + o número (1 a {n})", fim]):
        top._ctext(d, 935 + i * 60, ln, top._f(42), top.BR, 3, es)
    t = f"Segue o @{config.ARROBA.lstrip('@')} pra não perder o próximo"
    f = top._f(30)
    w = d.textlength(t, font=f)
    d.rounded_rectangle(((L - w) / 2 - 30, A - 130, (L + w) / 2 + 30, A - 62), 34, fill=top.AM)
    top._ctext(d, A - 121, t, f, es)
    return im


PALETAS_ANA = [((0xFF, 0xF8, 0xF4), (0xFB, 0xE3, 0xE8)), ((252, 243, 250), (238, 224, 244)),
               ((240, 250, 245), (212, 238, 224))]


def final_ana(v, n):
    from . import layout_ana as la
    topo, base = PALETAS_ANA[v % 3]
    img = _degrade(topo, base)
    av = la.avatar(300)
    if av:
        img.paste(av, ((L - av.width) // 2, 130), av)
    d = ImageDraw.Draw(img)
    _centro(d, 520, FINAIS_ANA[v % 3], la.serif(92), la.TEXTO)
    f2 = la.sans(44, "Medium")
    for i, ln in enumerate([f"comenta QUERO + o número (1 a {n})", "que eu te mando o link no direct"]):
        _centro(d, 660 + i * 62, ln, f2, la.TEXTO)
    la.botao_cta(img, 930, L, escala=1.1)
    _centro(d, A - 150, "me segue pra não perder o próximo achadinho", la.sans(34, "Medium"), la.ROSA_ESCURA)
    return img


# ================================================================== título do vídeo de abertura
def faixa_titulo(destino_png, v, dias_bf=None):
    """Título por cima do vídeo (PNG transparente): texto e posição (em cima ou embaixo) mudam a cada carrossel;
    nos 45 dias antes da Black Friday entra a etiqueta com a contagem."""
    ana = config.PERFIL == "ana"
    img = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    titulo, sub = (TITULOS_ANA if ana else TITULOS_GARIMPO)[v % N_TITULO]
    if ana:
        from . import layout_ana as la
        f = _ajustar(d, titulo, la.serif, 86, L - 200)
        fs = la.sans(38, "SemiBold")
        fundo, cor, cor_sub = (255, 248, 244, 225), la.TEXTO, la.ROSA_ESCURA
    else:
        f = _ajustar(d, titulo, lambda t: imagem._fonte(t, "Black"), 86, L - 200)
        fs = imagem._fonte(38, "SemiBold")
        fundo, cor, cor_sub = (45, 28, 12, 215), imagem.DOURADO_CLARO, imagem.BRANCO
    tw = d.textlength(sub, font=fs) + 70
    w = max(d.textlength(titulo, font=f), tw) + 90
    x0 = (L - w) / 2
    em_cima = v % 2 == 0
    y0 = 56 if em_cima else A - 290
    d.rounded_rectangle((x0, y0, x0 + w, y0 + 194), 44, fill=fundo)
    d.text(((L - d.textlength(titulo, font=f)) / 2, y0 + 22), titulo, font=f, fill=cor)
    xs = (L - tw) / 2
    d.text((xs, y0 + 122), sub, font=fs, fill=cor_sub)
    from .carrossel import _seta
    _seta(d, xs + tw - 50, y0 + 122 + fs.size * 0.62, cor_sub, tam=16)
    if dias_bf and 0 < dias_bf <= 45:
        fc = la.sans(34, "SemiBold") if ana else imagem._fonte(34, "SemiBold")
        t = f"faltam {dias_bf} dias pra Black Friday"
        wc = d.textlength(t, font=fc) + 60
        yc = y0 + 212 if em_cima else y0 - 70
        d.rounded_rectangle(((L - wc) / 2, yc, (L + wc) / 2, yc + 56), 28, fill=(205, 48, 36, 235))
        d.text((L / 2, yc + 29), t, font=fc, fill=(255, 255, 255), anchor="mm")
    img.save(destino_png)
