"""Arte vertical de story (1080x1920) a partir da arte do feed (1080x1350)."""
from PIL import Image, ImageDraw, ImageOps

from . import config
from .imagem import BRANCO, DOURADO, DOURADO_CLARO, ESCURO, FUNDO, _fonte

L, A = 1080, 1920


def _arredondar(img, raio):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.width - 1, img.height - 1], raio, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), m)
    return out


def gerar(arte_feed, destino):
    img = Image.new("RGB", (L, A), ESCURO)
    d = ImageDraw.Draw(img)
    f1 = _fonte(56, "Black")
    t1, t2 = "ACHADO NOVO ", "NO FEED"
    x = (L - d.textlength(t1 + t2, font=f1)) / 2
    d.text((x, 110), t1, font=f1, fill=BRANCO)
    d.text((x + d.textlength(t1, font=f1), 110), t2, font=f1, fill=DOURADO_CLARO)
    arte = Image.open(arte_feed).convert("RGB")
    arte = ImageOps.contain(arte, (940, 1175), Image.LANCZOS)
    arte = _arredondar(arte, 36)
    x0, y0 = (L - arte.width) // 2, 230
    d.rounded_rectangle([x0 - 8, y0 - 8, x0 + arte.width + 8, y0 + arte.height + 8], 42, fill=DOURADO)
    img.paste(arte, (x0, y0), arte)
    y = y0 + arte.height + 60
    d.rounded_rectangle([90, y, L - 90, y + 270], 48, fill=FUNDO)
    linhas = [("VAI NO ÚLTIMO POST E", _fonte(34, "SemiBold"), ESCURO, 34),
              ("COMENTA QUERO", _fonte(64, "Black"), DOURADO, 82),
              ("que o link chega no seu direct!", _fonte(34, "SemiBold"), ESCURO, 0)]
    yy = y + 36
    for t, f, cor, passo in linhas:
        d.text(((L - d.textlength(t, font=f)) / 2, yy), t, font=f, fill=cor)
        yy += passo + 18
    f4 = _fonte(34, "SemiBold")
    d.text(((L - d.textlength(config.ARROBA, font=f4)) / 2, A - 110), config.ARROBA, font=f4, fill=DOURADO_CLARO)
    img.save(destino, "JPEG", quality=90)
    return destino
