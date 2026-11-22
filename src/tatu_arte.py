"""Arte própria do Tatu Carão, o arqui-inimigo do Zé (aprovada pelo Fred em 22/11/2026, sem o carimbo VILÃO).

Vídeos ze_tatu_*: o texto de tela (assets/ze/textos.json) vai numa etiqueta de preço amarela e torta,
com letra roxa e o fim em vermelho; moldura roxa com tracejado amarelo e selo fixo
"TATU CARÃO" (o "arqui-inimigo do Zé" fica só na legenda). O Zé continua com a faixa marrom e dourada (src/ze_textos.py).

Prévia: python -m src.tatu_arte ze_tatu_chegada_semtrilha.mp4   → data/relatorios/tatu_arte/
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import config, ze_textos
from .imagem import _fonte

W, H = 1080, 1920
ROXO_ESC = (34, 8, 52)
ROXO = (98, 40, 150)
AMARELO = (255, 210, 0)
VERMELHO = (224, 40, 40)
TOPO = 150


def etiqueta(draw_img, box, fill, outline, furo=True):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(draw_img)
    h = y1 - y0
    bico = min(70, h * 0.45)
    pts = [(x0 + bico, y0), (x1, y0), (x1, y1), (x0 + bico, y1), (x0, y0 + h / 2)]
    d.polygon(pts, fill=fill)
    d.line(pts + [pts[0]], fill=outline, width=6, joint="curve")
    if furo:
        cx, cy, r = x0 + bico * 0.75, y0 + h / 2, 13
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 0), outline=outline, width=5)


def cartela(texto, destino):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tam = 64
    while True:
        f = _fonte(tam, "Black")
        linhas = ze_textos._quebrar(d, texto, f, W - 300)
        if len(linhas) <= 3 or tam <= 48:
            break
        tam -= 6
    alt = int(tam * 1.15)
    larg = max(d.textlength(l, font=f) for l in linhas) + 190
    caixa_h = alt * len(linhas) + 64
    camada = Image.new("RGBA", (int(larg) + 40, caixa_h + 40), (0, 0, 0, 0))
    sombra = Image.new("RGBA", camada.size, (0, 0, 0, 0))
    etiqueta(sombra, (20, 28, larg + 20, caixa_h + 28), (0, 0, 0, 140), (0, 0, 0, 0), furo=False)
    camada = Image.alpha_composite(camada, sombra.filter(ImageFilter.GaussianBlur(8)))
    etiqueta(camada, (14, 14, larg + 14, caixa_h + 14), AMARELO + (255,), ROXO_ESC + (255,))
    dc = ImageDraw.Draw(camada)
    for i, l in enumerate(linhas):
        cor = VERMELHO if i == len(linhas) - 1 and len(linhas) > 1 else ROXO_ESC
        x = 14 + 110 + (larg - 110 - 40 - dc.textlength(l, font=f)) / 2
        dc.text((x, 14 + 30 + i * alt), l, font=f, fill=cor)
    camada = camada.rotate(-3, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(camada, ((W - camada.width) // 2, TOPO))
    img.save(destino)


def moldura(destino):
    """Borda roxa com tracejado amarelo de etiqueta + selo fixo 'TATU CARÃO'."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    b = 22
    for r in [(0, 0, W, b), (0, H - b, W, H), (0, 0, b, H), (W - b, 0, W, H)]:
        d.rectangle(r, fill=ROXO_ESC + (255,))
    # tracejado amarelo
    m, passo, tr = 11, 46, 24
    for x in range(0, W, passo):
        d.line([(x, m), (x + tr, m)], fill=AMARELO, width=5)
        d.line([(x, H - m), (x + tr, H - m)], fill=AMARELO, width=5)
    for y in range(0, H, passo):
        d.line([(m, y), (m, y + tr)], fill=AMARELO, width=5)
        d.line([(W - m, y), (W - m, y + tr)], fill=AMARELO, width=5)
    # vinheta roxa nas bordas
    vin = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vin).rectangle([0, 0, W, H], fill=110)
    ImageDraw.Draw(vin).rounded_rectangle([90, 90, W - 90, H - 90], 120, fill=0)
    vin = vin.filter(ImageFilter.GaussianBlur(70))
    roxo = Image.new("RGBA", (W, H), ROXO + (255,))
    roxo.putalpha(vin)
    base = Image.alpha_composite(roxo, img)
    # selo fixo (acima da legenda do Instagram)
    selo = Image.new("RGBA", (620, 200), (0, 0, 0, 0))
    etiqueta(selo, (10, 10, 600, 130), ROXO + (255,), AMARELO + (255,))
    ds = ImageDraw.Draw(selo)
    f1, f2 = _fonte(62, "Black"), _fonte(34, "Bold")
    ds.text((115, 30), "TATU CARÃO", font=f1, fill=AMARELO)   # "arqui-inimigo" fica só na legenda (Fred, 22/11)
    selo = selo.rotate(4, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(selo, (40, 1290))
    # carimbo VILÃO no canto
    car = Image.new("RGBA", (330, 120), (0, 0, 0, 0))
    dc = ImageDraw.Draw(car)
    dc.rounded_rectangle([6, 6, 324, 114], 16, outline=VERMELHO, width=8)
    fc = _fonte(66, "Black")
    dc.text(((330 - dc.textlength("VILÃO", font=fc)) / 2, 18), "VILÃO", font=fc, fill=VERMELHO)
    car = car.rotate(12, expand=True, resample=Image.BICUBIC)
    pass  # sem carimbo VILÃO (Fred, 22/11)
    base.save(destino)


def gravar(video, saida):
    """Grava moldura, selo e etiquetas por cima do vídeo (sem música; o ze.py põe a do Tatu depois)."""
    from .ze import _ffmpeg
    video, saida = Path(video), Path(saida)
    tmp = saida.with_name(saida.stem + "_tatu")
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        moldura(tmp / "moldura.png")
        lista = ze_textos.frases(video.name)
        for i, (_, _, t) in enumerate(lista):
            cartela(t, tmp / f"c{i}.png")
        filtro = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
                  f"setsar=1[b];[b][1:v]overlay=0:0[v0]")
        for i, (a, b, _) in enumerate(lista):
            filtro += f";[v{i}][{i + 2}:v]overlay=0:0:enable='between(t,{a},{b})'[v{i + 1}]"
        filtro += f";[v{len(lista)}]format=yuv420p[vf]"
        cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-i", str(video), "-i", str(tmp / "moldura.png")]
        for i in range(len(lista)):
            cmd += ["-i", str(tmp / f"c{i}.png")]
        cmd += ["-filter_complex", filtro, "-map", "[vf]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium",
                "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(saida)]
        subprocess.run(cmd, check=True)
    finally:
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()
    return True


if __name__ == "__main__":
    pasta = config.RAIZ / "data" / "relatorios" / "tatu_arte"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in sys.argv[1:] or ["ze_tatu_chegada_semtrilha.mp4"]:
        gravar(config.RAIZ / "assets" / "ze" / nome, pasta / nome)
        print(f"✅ {pasta / nome}")
