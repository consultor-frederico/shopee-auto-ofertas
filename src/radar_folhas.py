"""Teste: monta uma folha por post com as fotos que a IA do radar olhou e os produtos que ela viu.
Lê data/relatorios/teste_radar.txt (rodado com RADAR_LISTAR_FOTOS=1) e grava em radar_fotos/."""
import io
import re
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

PASTA = Path("radar_fotos")
FONTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf"


def _fonte(tamanho, negrito=False):
    try:
        return ImageFont.truetype(FONTE % ("-Bold" if negrito else ""), tamanho)
    except Exception:
        return ImageFont.load_default()


def grupos():
    """[{perfil, urls, produtos}]: as fotos de cada post e o que a IA achou nelas."""
    saida, atual, lendo, antes = [], None, False, ""
    for linha in Path("data/relatorios/teste_radar.txt").read_text().splitlines():
        m = re.search(r"🖼️\s+(\S+)", linha)
        if m:
            if "🖼️" not in antes:   # cada post imprime as fotos juntas
                atual = {"perfil": "", "urls": [], "produtos": []}
                saida.append(atual)
            atual["urls"].append(m.group(1))
        elif "👁️  fotos de" in linha:
            lendo = True   # os produtos logo abaixo vieram dessas fotos
        elif lendo and (m := re.search(r"🔥 .*\(@([^)]+)\): (.+?) →", linha)):
            atual["perfil"] = m.group(1)
            atual["produtos"].append(m.group(2))
        else:
            lendo = False
        antes = linha
    return [g for g in saida if g["produtos"]]


def folha(g):
    fotos = []
    for u in g["urls"]:
        try:
            r = requests.get(u, timeout=30)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            img.thumbnail((540, 675))
            fotos.append(img)
        except Exception as e:
            print(f"   ⚠️  foto: {str(e)[:80]}")
    if not fotos:
        return None
    colunas = min(len(fotos), 2)
    topo = 70 + 38 * len(g["produtos"])
    img = Image.new("RGB", (540 * colunas, topo + 675 * ((len(fotos) + 1) // 2)), (40, 28, 20))
    d = ImageDraw.Draw(img)
    d.text((16, 14), f"@{g['perfil']}", fill=(212, 175, 55), font=_fonte(32, True))
    for i, p in enumerate(g["produtos"]):
        d.text((16, 62 + 38 * i), f"• {p}"[:70], fill=(255, 255, 255), font=_fonte(24))
    for i, f in enumerate(fotos):
        img.paste(f, ((i % colunas) * 540, topo + (i // colunas) * 675))
    return img


if __name__ == "__main__":
    PASTA.mkdir(exist_ok=True)
    for n, g in enumerate(grupos(), 1):
        img = folha(g)
        if img:
            nome = PASTA / f"{n:02d}_{g['perfil']}.jpg"
            img.save(nome, "JPEG", quality=82)
            print(f"🖼️  {nome}: {', '.join(g['produtos'])}")
