"""Gera um Reels (1080x1920, ~8s, MP4 H.264) a partir da foto da oferta, sem música.

Linha do tempo:
  0,0s  logo + foto com zoom lento
  0,6s  título entra
  1,4s  preço entra deslizando
  2,2s  selo de desconto "salta"
  2,8s  nota e vendas
  3,6s  faixa "COMENTE EU QUERO" sobe e pulsa até o fim
"""
import math
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageOps

from . import config
from .imagem import (FUNDO, SOMBRA, faixa_arco_iris, BRANCO, CINZA, DOURADO, DOURADO_CLARO, ESCURO, LARANJA,
                     _baixar_foto, _brl, _estrela, _fonte, selo_loja)

L, A = 1080, 1920
FPS = 30
DURACAO = 8.0


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _pop(t):
    """Escala com leve "quique": 0 → ~1.05 → 1."""
    t = max(0.0, min(1.0, t))
    return _ease(t) + 0.15 * math.sin(math.pi * t)


def _fundo_estatico(oferta, foto):
    """Partes que não se mexem: fundo e logo."""
    base = Image.new("RGB", (L, A), FUNDO)
    try:
        logo = Image.open(config.LOGO).convert("RGBA")
        logo = ImageOps.contain(logo, (340, 200), Image.LANCZOS)
        base.paste(logo, ((L - logo.width) // 2, 70), logo)
    except Exception:
        pass
    return base


def _quadro(t, base, foto, oferta):
    img = base.copy()
    d = ImageDraw.Draw(img)

    # Cartão da foto com zoom lento (1.00 → 1.08)
    cx0, cy0, cx1, cy1 = 70, 300, L - 70, 300 + 940
    d.rounded_rectangle([cx0 + 6, cy0 + 10, cx1 + 6, cy1 + 10], 44, fill=SOMBRA)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], 44, fill=BRANCO)
    if foto is not None:
        z = 1 + 0.08 * (t / DURACAO)
        alvo = (int((cx1 - cx0 - 80) * z), int((cy1 - cy0 - 80) * z))
        f = ImageOps.contain(foto, alvo, Image.BILINEAR)
        # recorta o excesso para não vazar do cartão
        jan_w, jan_h = cx1 - cx0 - 40, cy1 - cy0 - 40
        ox, oy = max(0, (f.width - jan_w) // 2), max(0, (f.height - jan_h) // 2)
        f = f.crop((ox, oy, ox + min(f.width, jan_w), oy + min(f.height, jan_h)))
        img.paste(f, (cx0 + (cx1 - cx0 - f.width) // 2, cy0 + (cy1 - cy0 - f.height) // 2))

    # Selo da loja
    selo_loja(d, oferta, cx0 + 30, cy0 + 30, escala=1.1)

    # Selo de desconto
    if oferta.get("desconto") and t >= 2.2:
        s = _pop((t - 2.2) / 0.45)
        r = int(120 * s)
        if r > 8:
            sx, sy = cx1 - 50, cy0 + 50
            d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=DOURADO, outline=BRANCO, width=8)
            if s > 0.7:
                f1, f2 = _fonte(int(74 * s), "Black"), _fonte(int(38 * s), "Bold")
                t1, t2 = f"-{oferta['desconto']}%", "OFF"
                d.text((sx - d.textlength(t1, font=f1) / 2, sy - 62 * s), t1, font=f1, fill=BRANCO)
                d.text((sx - d.textlength(t2, font=f2) / 2, sy + 22 * s), t2, font=f2, fill=BRANCO)

    # Título (desliza da esquerda)
    y = cy1 + 60
    if t >= 0.6:
        k = _ease((t - 0.6) / 0.5)
        f_tit = _fonte(60, "ExtraBold")
        d.text((70 - (1 - k) * 300, y), oferta["titulo"], font=f_tit,
               fill=_mix(FUNDO, ESCURO, k))

    # Preço (sobe)
    y2 = y + 100
    if t >= 1.4:
        k = _ease((t - 1.4) / 0.5)
        dy = (1 - k) * 80
        x = 70
        f_de, f_rs, f_preco = _fonte(42, "Medium"), _fonte(54, "Bold"), _fonte(130, "Black")
        if oferta.get("preco_de"):
            de = f"R$ {_brl(oferta['preco_de'])}"
            d.text((x, y2 + 50 + dy), de, font=f_de, fill=_mix(FUNDO, CINZA, k))
            w = d.textlength(de, font=f_de)
            d.line([x - 4, y2 + 77 + dy, x + w + 4, y2 + 77 + dy], fill=_mix(FUNDO, CINZA, k), width=5)
            x += w + 30
        d.text((x, y2 + 44 + dy), "R$", font=f_rs, fill=_mix(FUNDO, DOURADO, k))
        x += d.textlength("R$", font=f_rs) + 12
        d.text((x, y2 - 20 + dy), oferta["preco_fmt"], font=f_preco, fill=_mix(FUNDO, LARANJA, k))

    # Nota e vendas
    if t >= 2.8:
        k = _ease((t - 2.8) / 0.4)
        yi = y2 + 175
        cor = _mix(FUNDO, CINZA, k)
        _estrela(d, 70 + 22, yi + 25, 24, _mix(FUNDO, DOURADO, k))
        nota = f"{oferta['nota']:.1f}".replace(".", ",")
        vendas = f"{oferta['vendas']:,}".replace(",", ".")
        d.text((70 + 54, yi), f"{nota}   •   {vendas}+ vendidos", font=_fonte(40, "SemiBold"), fill=cor)

    # Faixa de chamada (sobe e pulsa)
    if t >= 3.6:
        k = _ease((t - 3.6) / 0.4)
        h = 170
        topo = A - h * k
        d.rectangle([0, topo, L, A], fill=ESCURO)
        faixa_arco_iris(d, int(topo) - 10, 10)
        pulso = 1 + 0.05 * math.sin((t - 4.0) * 2 * math.pi * 1.1) if t > 4.0 else 1
        f_cta = _fonte(int(52 * pulso), "ExtraBold")
        partes = [("COMENTE ", BRANCO), ("EU QUERO", DOURADO_CLARO)]
        x = (L - sum(d.textlength(p, font=f_cta) for p, _ in partes)) / 2
        for p, cor in partes:
            d.text((x, topo + 30), p, font=f_cta, fill=cor)
            x += d.textlength(p, font=f_cta)
        f2 = _fonte(36, "SemiBold")
        sub = "que eu te mando o link no direct"
        d.text(((L - d.textlength(sub, font=f2)) / 2, topo + 100), sub, font=f2, fill="#CFC6B8")
    return img


def _mix(c1, c2, k):
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def gerar(oferta: dict, destino, foto: Image.Image = None):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            raise RuntimeError("ffmpeg não encontrado (instale ffmpeg ou imageio-ffmpeg).")
    if foto is None:
        try:
            foto = _baixar_foto(oferta["imagem"])
        except Exception as e:
            print(f"⚠️  Reels sem foto ({e}).")
    base = _fundo_estatico(oferta, foto)
    cmd = [ffmpeg, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{L}x{A}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
           "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "128k", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(DURACAO * FPS)):
        proc.stdin.write(_quadro(i / FPS, base, foto, oferta).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falhou ao gerar o Reels.")
    return destino
