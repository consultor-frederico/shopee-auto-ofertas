"""Visual próprio da Ana Novo Achados (@ananovoachados) — propositalmente diferente do Garimpo VIP.

Paleta leve e feminina (creme, rosa-blush e ameixa). Foto numa moldura em arco, título em fonte
serifada, preço em pílula menta, adesivo de desconto inclinado e chamada em botão contornado.
"""
import math
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config, marcas

PASTA = config.RAIZ / "assets" / "ana"
SERIF = PASTA / "DMSerifDisplay-Regular.ttf"
SANS = PASTA / "DMSans.ttf"

# Paleta leve e feminina: creme e rosa-blush, rosa no destaque e texto ameixa
TOPO_COR, BASE_COR = (0xFF, 0xF8, 0xF4), (0xFB, 0xE3, 0xE8)
TEXTO = "#4A2C3F"          # ameixa (títulos e textos)
ROSA = "#F2A7B8"           # pílula do preço e adesivo
ROSA_ESCURA = "#D9668A"    # linhas, "QUERO" e detalhes
CINZA = "#A08893"          # malva (preço antigo e avaliação)
BRANCO = "#FFFFFF"
LOJAS = {"shopee": ("Shopee", "#EE4D2D"), "aliexpress": ("AliExpress", "#E43225"),
         **{p: (m["nome"], m["cor"]) for p, m in marcas.MARCAS.items()}}


def sans(tam, peso="Bold"):
    f = ImageFont.truetype(str(SANS), tam)
    try:
        f.set_variation_by_name(peso)
    except Exception:
        pass
    return f


def serif(tam):
    return ImageFont.truetype(str(SERIF), tam)


def _brl(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def degrade(l, a):
    img = Image.new("RGB", (l, a))
    d = ImageDraw.Draw(img)
    for y in range(a):
        k = y / (a - 1)
        d.line([(0, y), (l, y)], fill=tuple(int(c1 + (c2 - c1) * k) for c1, c2 in zip(TOPO_COR, BASE_COR)))
    return img


def logo(largura=330):
    """Logo da Ana (assets/ana/logo.png com fundo transparente), pintado de ameixa."""
    img = Image.open(config.LOGO).convert("RGBA")
    img = Image.merge("RGBA", (*Image.new("RGB", img.size, TEXTO).split(), img.getchannel("A")))  # logo em ameixa
    return ImageOps.contain(img, (largura, 10_000), Image.LANCZOS)


ROSTO = PASTA / "ana.jpg"        # a personagem Ana (versão jovem da Ana de verdade)
ROSTO_CORTE = (180, 120, 640, 580)  # recorte do rosto na foto 825x1024


def avatar(diam):
    """Rosto da Ana num círculo com anel rosa (None se a foto não existir)."""
    if not ROSTO.exists():
        return None
    r = Image.open(ROSTO).convert("RGB").crop(ROSTO_CORTE).resize((diam, diam), Image.LANCZOS)
    m = Image.new("L", (diam, diam), 0)
    ImageDraw.Draw(m).ellipse([0, 0, diam - 1, diam - 1], fill=255)
    anel = Image.new("RGBA", (diam + 12, diam + 12), (0, 0, 0, 0))
    ImageDraw.Draw(anel).ellipse([0, 0, diam + 11, diam + 11], fill=ROSA_ESCURA)
    anel.paste(r, (6, 6), m)
    return anel


def mascara_arco(l, a):
    m = Image.new("L", (l, a), 0)
    d = ImageDraw.Draw(m)
    r = l // 2
    d.ellipse([0, 0, l - 1, 2 * r], fill=255)
    d.rounded_rectangle([0, r, l - 1, a - 1], 36, fill=255)
    d.rectangle([0, r, l - 1, a - 60], fill=255)
    return m


def colar_foto_no_arco(img, foto, caixa, zoom=1.0):
    x0, y0, x1, y1 = caixa
    l, a = x1 - x0, y1 - y0
    m = mascara_arco(l, a)
    # contorno menta afastado da moldura (arco duplo, aberto embaixo)
    g, esp = 20, 4
    X0, Y0, X1 = x0 - g, y0 - g, x1 + g
    r = (X1 - X0) / 2
    dd = ImageDraw.Draw(img)
    dd.arc([X0, Y0, X1, Y0 + 2 * r], 180, 360, fill=ROSA_ESCURA, width=esp)
    for x in (X0 + esp / 2, X1 - esp / 2):
        dd.line([(x, Y0 + r), (x, y1 - 40)], fill=ROSA_ESCURA, width=esp)
    moldura = Image.new("RGB", (l, a), BRANCO)
    if foto is not None:
        alvo = (int((l - 70) * zoom), int((a - 120) * zoom))
        f = ImageOps.contain(foto, alvo, Image.LANCZOS if zoom == 1.0 else Image.BILINEAR)
        moldura.paste(f, ((l - f.width) // 2, (a - f.height) // 2 + 30))
    img.paste(moldura, (x0, y0), m)


def adesivo(img, cx, cy, texto1, texto2, r=118, angulo=-12, escala=1.0):
    """Adesivo redondo de bordas onduladas, levemente girado."""
    if escala <= 0.01:
        return
    tam = int(2 * r + 40)
    a = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(a)
    c = tam / 2
    pts = []
    for i in range(48):
        ang = 2 * math.pi * i / 48
        rr = r * (1 + 0.06 * math.cos(ang * 12))
        pts.append((c + rr * math.cos(ang), c + rr * math.sin(ang)))
    d.polygon(pts, fill=ROSA)
    d.ellipse([c - r * 0.82, c - r * 0.82, c + r * 0.82, c + r * 0.82], outline=TEXTO, width=3)
    f1, f2 = sans(int(r * 0.46), "Black"), sans(int(r * 0.26), "Bold")
    d.text((c - d.textlength(texto1, font=f1) / 2, c - r * 0.44), texto1, font=f1, fill=TEXTO)
    d.text((c - d.textlength(texto2, font=f2) / 2, c + r * 0.10), texto2, font=f2, fill=TEXTO)
    a = a.rotate(angulo, resample=Image.BICUBIC)
    if escala != 1.0:
        n = max(1, int(tam * escala))
        a = a.resize((n, n), Image.BICUBIC)
    img.paste(a, (int(cx - a.width / 2), int(cy - a.height / 2)), a)


def selo_loja(d, oferta, x, y):
    nome, cor = LOJAS.get(oferta.get("plataforma") or "shopee", ("Loja", TEXTO))
    f = sans(28, "Bold")
    t = f"na {nome}" + (" · internacional" if oferta.get("internacional") else "")   # 🌎 vem de fora
    w = d.textlength(t, font=f)
    d.rounded_rectangle([x, y, x + w + 56, y + 50], 25, fill=BRANCO, outline=cor, width=3)
    d.ellipse([x + 16, y + 18, x + 30, y + 32], fill=cor)
    d.text((x + 40, y + 9), t, font=f, fill=cor)
    return w + 56


def quebrar(d, texto, fonte, largura, max_linhas=2):
    linhas, atual = [], ""
    for p in texto.split():
        teste = f"{atual} {p}".strip()
        if d.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1].rstrip(".,") + "…"
    return linhas


def bloco_texto(img, oferta, y, largura_total):
    """Título serifado, preço em pílula e avaliação — tudo centralizado. Devolve o y final."""
    d = ImageDraw.Draw(img)
    l = largura_total
    f_tit = serif(68)
    for linha in quebrar(d, oferta["titulo"], f_tit, l - 160, max_linhas=2):
        d.text(((l - d.textlength(linha, font=f_tit)) / 2, y), linha, font=f_tit, fill=TEXTO)
        y += 78
    y += 26
    preco = f"R$ {oferta['preco_fmt']}"
    f_p = sans(78, "Black")
    wp = d.textlength(preco, font=f_p)
    de = f"de R$ {_brl(oferta['preco_de'])}" if oferta.get("preco_de") else ""
    f_de = sans(34, "Medium")
    wd = d.textlength(de, font=f_de) + 24 if de else 0
    x = (l - (wd + wp + 70)) / 2
    if de:
        d.text((x, y + 34), de, font=f_de, fill=CINZA)
        d.line([x - 2, y + 56, x + wd - 22, y + 56], fill=CINZA, width=3)
        x += wd
    d.rounded_rectangle([x, y, x + wp + 70, y + 110], 55, fill=ROSA)
    d.text((x + 35, y + 8), preco, font=f_p, fill=TEXTO)
    y += 136
    nota = (f"{oferta['avaliacao_pct']:.0f}% avaliações positivas" if oferta.get("avaliacao_pct")
                else f"{oferta['nota']:.1f}".replace(".", ","))
    vendas = f"{oferta['vendas']:,}".replace(",", ".")
    info = f"{nota if '%' in nota else 'nota ' + nota}  ·  {vendas}+ vendidos"
    if marcas.eh_marca(oferta):
        info = marcas.texto_oficial(oferta)
    f_i = sans(32, "Medium")
    d.text(((l - d.textlength(info, font=f_i)) / 2, y), info, font=f_i, fill=CINZA)
    return y + 46


def botao_cta(img, cy, largura_total, escala=1.0):
    d = ImageDraw.Draw(img)
    f1, f2 = sans(int(44 * escala), "Bold"), sans(int(44 * escala), "Black")
    t1, t2, t3 = "comenta ", "QUERO", " e recebe o link"
    w = sum(d.textlength(t, font=f) for t, f in ((t1, f1), (t2, f2), (t3, f1)))
    h = int(96 * escala)
    x0 = (largura_total - w) / 2 - 50
    d.rounded_rectangle([x0, cy - h / 2, x0 + w + 100, cy + h / 2], h // 2, fill=BRANCO, outline=ROSA_ESCURA, width=4)
    x = x0 + 50
    ty = cy - 30 * escala
    for t, f, cor in ((t1, f1, TEXTO), (t2, f2, ROSA_ESCURA), (t3, f1, TEXTO)):
        d.text((x, ty), t, font=f, fill=cor)
        x += d.textlength(t, font=f)


# ---------------------------------------------------------------- foto (1080x1350)
def gerar_foto(oferta, destino, foto=None):
    L, A = 1080, 1350
    img = degrade(L, A)
    x = 60
    av = avatar(118)
    if av:
        img.paste(av, (x, 30), av)
        x += av.width + 22
    lg = logo(150)
    img.paste(lg, (x, 36), lg)
    d = ImageDraw.Draw(img)
    f = sans(30, "Medium")
    t = "achadinho do dia"
    d.text((L - 70 - d.textlength(t, font=f), 76), t, font=f, fill=ROSA_ESCURA)
    caixa = (180, 185, L - 180, 815)
    colar_foto_no_arco(img, foto, caixa)
    d = ImageDraw.Draw(img)
    selo_loja(d, oferta, caixa[0] + 30, caixa[3] - 80)
    if oferta.get("desconto"):
        adesivo(img, caixa[2] - 10, caixa[1] + 170, f"-{oferta['desconto']}%", "OFF")
    bloco_texto(img, oferta, 845, L)
    botao_cta(img, A - 72, L)
    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino


# ---------------------------------------------------------------- Reels (1080x1920, 8s)
MUSICAS = PASTA / "musicas"   # trilhas só da Ana (nunca as do Garimpo VIP)


def _trilha(duracao):
    """Entrada de áudio do ffmpeg: uma música da Ana sorteada (com fade no fim) ou silêncio."""
    import random
    # A trilha agora entra depois, no Reels inteiro (src/ze.py: emendar_final), junto com a Ana no começo/fim
    # e mais baixa quando ela fala. Aqui sai sem música para não ficarem duas por cima uma da outra.
    faixas = []
    if not faixas:
        return ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    return ["-i", str(random.choice(faixas)), "-af",
            f"volume=0.8,afade=t=in:d=0.3,afade=t=out:st={duracao - 1.2}:d=1.2"]


def gerar_reels(oferta, destino, foto=None, duracao=8.0, fps=30):
    L, A = 1080, 1920
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    base = degrade(L, A)
    av = avatar(210)
    if av:
        lg = logo(270)
        x = (L - (av.width + 40 + lg.width)) // 2
        base.paste(av, (x, 110), av)
        base.paste(lg, (x + av.width + 40, 110 + (av.height - lg.height) // 2), lg)
    else:
        lg = logo(340)
        base.paste(lg, ((L - lg.width) // 2, 90), lg)
    caixa = (130, 400, L - 130, 1230)
    texto = Image.new("RGBA", (L, 480), (0, 0, 0, 0))
    bloco_texto(texto, oferta, 0, L)

    def quadro(t):
        img = base.copy()
        colar_foto_no_arco(img, foto, caixa, zoom=1 + 0.07 * t / duracao)
        d = ImageDraw.Draw(img)
        if t >= 0.4:
            selo_loja(d, oferta, caixa[0] + 30, caixa[3] - 80)
        if oferta.get("desconto") and t >= 1.0:
            k = min(1.0, (t - 1.0) / 0.35)
            esc = k * (1 + 0.18 * math.sin(math.pi * k))
            adesivo(img, caixa[2] - 10, caixa[1] + 190, f"-{oferta['desconto']}%", "OFF",
                    r=130, angulo=-12 + 8 * math.sin(t * 1.5), escala=esc)
        if t >= 0.6:   # texto sobe com fade
            k = min(1.0, (t - 0.6) / 0.5)
            camada = texto.copy()
            camada.putalpha(camada.getchannel("A").point(lambda v: int(v * k)))
            img.paste(camada, (0, int(1275 + 40 * (1 - k))), camada)
        if t >= 2.4:
            pulso = 1 + 0.04 * math.sin((t - 2.4) * 2 * math.pi * 1.1)
            botao_cta(img, A - 150, L, escala=pulso)
        return img

    cmd = [ffmpeg, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{L}x{A}", "-r", str(fps), "-i", "-",
           *_trilha(duracao),
           "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "128k", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(duracao * fps)):
        proc.stdin.write(quadro(i / fps).convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falhou ao gerar o Reels.")
    return destino


# ---------------------------------------------------------------- story (1080x1920)
def gerar_story(arte_feed, destino):
    """Story da Ana feito da arte do feed (que já traz o rosto dela e o botão do QUERO)."""
    L, A = 1080, 1920
    img = degrade(L, A)
    d = ImageDraw.Draw(img)
    f = serif(72)
    t = "achadinho novo no feed"
    d.text(((L - d.textlength(t, font=f)) / 2, 150), t, font=f, fill=TEXTO)
    arte = ImageOps.contain(Image.open(arte_feed).convert("RGB"), (900, 1125), Image.LANCZOS)
    m = Image.new("L", arte.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, arte.width - 1, arte.height - 1], 40, fill=255)
    x0, y0 = (L - arte.width) // 2, 300
    d.rounded_rectangle([x0 - 8, y0 - 8, x0 + arte.width + 8, y0 + arte.height + 8], 48, fill=ROSA_ESCURA)
    img.paste(arte, (x0, y0), m)
    y = y0 + arte.height + 90
    f1, f2 = sans(44, "Medium"), sans(44, "Black")
    t1, t2 = "vai no último post e comenta ", "QUERO"
    x = (L - d.textlength(t1, font=f1) - d.textlength(t2, font=f2)) / 2
    d.text((x, y), t1, font=f1, fill=TEXTO)
    d.text((x + d.textlength(t1, font=f1), y), t2, font=f2, fill=ROSA_ESCURA)
    f3 = sans(34, "Medium")
    d.text(((L - d.textlength(config.ARROBA, font=f3)) / 2, A - 120), config.ARROBA, font=f3, fill=ROSA_ESCURA)
    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino
