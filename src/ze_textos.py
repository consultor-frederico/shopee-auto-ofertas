"""Texto na tela dos Reels do Zé: quase todo mundo assiste sem som, então a frase do roteiro vai gravada no vídeo.

As frases e os tempos ficam em assets/ze/textos.json ({"ze_x.mp4": [[início, fim, "TEXTO"], ...]}).
O vídeo sai em 1080x1920 com o áudio original; vídeo sem frases cadastradas não é mexido.

Prévia: python -m src.ze_textos ze_salario_semtrilha.mp4   → data/relatorios/ze_textos/
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from . import config
from .imagem import _fonte

ARQ = config.RAIZ / "assets" / "ze" / "textos.json"
W, H = 1080, 1920
TOPO = 250            # abaixo da barra do Instagram, acima do rosto do Zé
MARROM = (36, 21, 10, 225)
DOURADO = "#E2BE68"


def frases(nome):
    try:
        return json.loads(ARQ.read_text(encoding="utf-8")).get(nome) or []
    except (OSError, ValueError):
        return []


def _quebrar(d, texto, fonte, largura):
    linhas, atual = [], ""
    for p in texto.split():
        teste = f"{atual} {p}".strip()
        if d.textlength(teste, font=fonte) <= largura or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    return linhas + [atual]


def cartela(texto, destino):
    """PNG transparente 1080x1920 com a frase numa faixa marrom de cantos redondos, letra branca e dourada."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tam = 78
    while True:
        f = _fonte(tam, "Bold")
        linhas = _quebrar(d, texto, f, W - 200)
        if len(linhas) <= 3 or tam <= 50:
            break
        tam -= 6
    alt = int(tam * 1.18)
    caixa_h = alt * len(linhas) + 70
    larg = max(d.textlength(l, font=f) for l in linhas) + 110
    x0 = (W - larg) / 2
    d.rounded_rectangle([x0, TOPO, x0 + larg, TOPO + caixa_h], 40, fill=MARROM, outline=DOURADO, width=5)
    for i, l in enumerate(linhas):
        cor = DOURADO if i == len(linhas) - 1 and len(linhas) > 1 else "white"
        d.text(((W - d.textlength(l, font=f)) / 2, TOPO + 30 + i * alt), l, font=f, fill=cor)
    img.save(destino)


def gravar(video, saida):
    """Grava as frases do vídeo por cima. Devolve False (sem mexer) se o vídeo não tem frases cadastradas."""
    from .ze import _ffmpeg
    lista = frases(Path(video).name)
    if not lista:
        return False
    saida = Path(saida)
    pngs = []
    for i, (_, _, texto) in enumerate(lista):
        p = saida.with_name(f"{saida.stem}_t{i}.png")
        cartela(texto, p)
        pngs.append(p)
    filtro = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v0]"
    for i, (ini, fim, _) in enumerate(lista):
        filtro += f";[v{i}][{i + 1}:v]overlay=0:0:enable='between(t,{ini},{fim})'[v{i + 1}]"
    filtro += f";[v{len(lista)}]format=yuv420p[vf]"
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-i", str(video)]
    for p in pngs:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex", filtro, "-map", "[vf]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium",
            "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(saida)]
    try:
        subprocess.run(cmd, check=True)
    finally:
        for p in pngs:
            p.unlink(missing_ok=True)
    return True


if __name__ == "__main__":
    pasta = config.RAIZ / "data" / "relatorios" / "ze_textos"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in sys.argv[1:] or [k for k in json.loads(ARQ.read_text(encoding="utf-8")) if not k.startswith("_")]:
        ok = gravar(config.RAIZ / "assets" / "ze" / nome, pasta / nome)
        print(("✅ " if ok else "⏭️  sem texto: ") + nome)
