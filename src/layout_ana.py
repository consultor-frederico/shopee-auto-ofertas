"""Visual próprio da Ana Novo Achados (@ananovoachados) — propositalmente diferente do Garimpo VIP.

Cores do logo da Ana (azul-noite e verde-menta). Foto numa moldura em arco, título em fonte
serifada, preço em pílula menta, adesivo de desconto inclinado e chamada em botão contornado.
"""
import math
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config

PASTA = config.RAIZ / "assets" / "ana"
SERIF = PASTA / "DMSerifDisplay-Regular.ttf"
SANS = PASTA / "DMSans.ttf"

# Paleta tirada do logo da Ana
TOPO_COR, BASE_COR = (0x12, 0x11, 0x1F), (0x1E, 0x1C, 0x36)
NOITE = "#12111F"
MENTA = "#7CDACA"
MENTA_ESCURA = "#3E9C8E"
CINZA = "#9B99B5"
BRANCO = "#FFFFFF"
LOJAS = {"shopee": ("Shopee", "#EE4D2D"), "aliexpress": ("AliExpress", "#E43225")}


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
    """Logo da Ana (assets/ana/logo.png, menta com fundo transparente)."""
    img = Image.open(config.LOGO).convert("RGBA")
    return ImageOps.contain(img, (largura, 10_000), Image.LANCZOS)


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
    dd.arc([X0, Y0, X1, Y0 + 2 * r], 180, 360, fill=MENTA, width=esp)
    for x in (X0 + esp / 2, X1 - esp / 2):
        dd.line([(x, Y0 + r), (x, y1 - 40)], fill=MENTA, width=esp)
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
    d.polygon(pts, fill=MENTA)
    d.ellipse([c - r * 0.82, c - r * 0.82, c + r * 0.82, c + r * 0.82], outline=NOITE, width=3)
    f1, f2 = sans(int(r * 0.46), "Black"), sans(int(r * 0.26), "Bold")
    d.text((c - d.textlength(texto1, font=f1) / 2, c - r * 0.44), texto1, font=f1, fill=NOITE)
    d.text((c - d.textlength(texto2, font=f2) / 2, c + r * 0.10), texto2, font=f2, fill=NOITE)
    a = a.rotate(angulo, resample=Image.BICUBIC)
    if escala != 1.0:
        n = max(1, int(tam * escala))
        a = a.resize((n, n), Image.BICUBIC)
    img.paste(a, (int(cx - a.width / 2), int(cy - a.height / 2)), a)


def selo_loja(d, oferta, x, y):
    nome, cor = LOJAS.get(oferta.get("plataforma") or "shopee", ("Loja", NOITE))
    f = sans(28, "Bold")
    t = f"na {nome}"
    w = d.textlength(t, font=f)
    d.rounded_rectangle([x, y, x + w + 56, y + 50], 25, fill=BRANCO, outline=cor, width=3)
    d.ellipse([x + 16, y + 18, x + 30, y + 32], fill=cor)
    d.text((x + 40, y + 9), t, font=f, fill=cor)


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
        d.text(((l - d.textlength(linha, font=f_tit)) / 2, y), linha, font=f_tit, fill=BRANCO)
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
    d.rounded_rectangle([x, y, x + wp + 70, y + 110], 55, fill=MENTA)
    d.text((x + 35, y + 8), preco, font=f_p, fill=NOITE)
    y += 136
    nota = (f"{oferta['avaliacao_pct']:.0f}% aprovação" if oferta.get("avaliacao_pct")
                else f"{oferta['nota']:.1f}".replace(".", ","))
    vendas = f"{oferta['vendas']:,}".replace(",", ".")
    info = f"{nota if '%' in nota else 'nota ' + nota}  ·  {vendas}+ vendidos"
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
    d.rounded_rectangle([x0, cy - h / 2, x0 + w + 100, cy + h / 2], h // 2, outline=MENTA, width=4)
    x = x0 + 50
    ty = cy - 30 * escala
    for t, f, cor in ((t1, f1, BRANCO), (t2, f2, MENTA), (t3, f1, BRANCO)):
        d.text((x, ty), t, font=f, fill=cor)
        x += d.textlength(t, font=f)


# ---------------------------------------------------------------- foto (1080x1350)
def gerar_foto(oferta, destino, foto=None):
    L, A = 1080, 1350
    img = degrade(L, A)
    lg = logo(150)
    img.paste(lg, (70, 36), lg)
    d = ImageDraw.Draw(img)
    f = sans(30, "Medium")
    t = "achadinho do dia"
    d.text((L - 70 - d.textlength(t, font=f), 76), t, font=f, fill=MENTA)
    caixa = (170, 185, L - 170, 860)
    colar_foto_no_arco(img, foto, caixa)
    d = ImageDraw.Draw(img)
    selo_loja(d, oferta, caixa[0] + 30, caixa[3] - 80)
    if oferta.get("desconto"):
        adesivo(img, caixa[2] - 10, caixa[1] + 170, f"-{oferta['desconto']}%", "OFF")
    bloco_texto(img, oferta, 892, L)
    botao_cta(img, A - 86, L)
    img.save(destino, "JPEG", quality=90, optimize=True)
    return destino


# ---------------------------------------------------------------- Reels (1080x1920, 8s)
def gerar_reels(oferta, destino, foto=None, duracao=8.0, fps=30):
    L, A = 1080, 1920
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    base = degrade(L, A)
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
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
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
