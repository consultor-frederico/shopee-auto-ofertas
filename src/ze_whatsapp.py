"""Vídeos do Zé Garimpo prontos para o WhatsApp (status, grupos, conversas).

Vídeo não aceita link clicável, então cada vídeo termina com um cartão "SIGA O ZÉ NO INSTAGRAM
@garimpovip4 — toque no link aqui embaixo" e vai junto com uma legenda que traz o link.
No WhatsApp o link da legenda fica clicável (inclusive no status) e mostra a prévia do perfil.

Uso: python -m src.ze_whatsapp            → gera todos em saida/whatsapp/
     python -m src.ze_whatsapp ze_rio     → só um
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from . import config
from .imagem import _fonte

RAIZ = config.RAIZ
LOGO = RAIZ / "assets" / "logo.png"
SAIDA = RAIZ / "saida" / "whatsapp"
INSTAGRAM = "https://www.instagram.com/garimpovip4"
ARROBA = "@garimpovip4"
CARTAO_S = 3.0   # duração do cartão final
L, A = 720, 1280
OURO, ESCURO, CREME = (212, 165, 55), (36, 21, 10), (243, 239, 232)

CHAMADAS = [
    "TODO DIA UM ACHADO NOVO",
    "O ZÉ GARIMPA, VOCÊ ECONOMIZA",
    "SÓ ACHADO DIFERENTE DA SHOPEE",
    "PRODUTO BOM, PREÇO DE GARIMPO",
]

LEGENDAS = [
    "O Zé Garimpo vasculha a Shopee todo dia atrás de achado diferente (nada de produto repetido 😉)\n"
    "Segue lá no Instagram 👉 {link}",
    "Cansou de ver sempre os mesmos produtos? O Zé só traz achado de verdade ⛏️💎\n{link}",
    "Tá procurando alguma coisa? Comenta lá no Instagram que o Zé acha pra você 🔎\n{link}",
    "Achadinhos da Shopee garimpados todo dia pelo Zé ⛏️\nVem pro Garimpo VIP 👉 {link}",
]


def _centro(d, y, texto, tam, cor, peso="Bold"):
    f = _fonte(tam, peso)
    w = d.textlength(texto, font=f)
    d.text(((L - w) / 2, y), texto, font=f, fill=cor)


def faixa(chamada, destino):
    img = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 70, L - 40, 150), radius=40, fill=ESCURO + (215,))
    _centro(d, 92, chamada, 34, OURO, "ExtraBold")
    img.save(destino)


def cartao(destino):
    img = Image.new("RGBA", (L, A), ESCURO + (238,))
    d = ImageDraw.Draw(img)
    logo = Image.open(LOGO).convert("RGBA")
    logo = logo.resize((340, int(340 * logo.height / logo.width)))
    x, y = (L - logo.width) // 2, 250
    d.ellipse((L / 2 - 205, y + logo.height / 2 - 205, L / 2 + 205, y + logo.height / 2 + 205), fill=CREME)
    img.alpha_composite(logo, (x, y))
    _centro(d, 685, "SIGA O ZÉ NO INSTAGRAM", 44, CREME, "ExtraBold")
    d.rounded_rectangle((90, 755, L - 90, 865), radius=55, fill=OURO)
    _centro(d, 775, ARROBA, 62, ESCURO, "ExtraBold")
    _centro(d, 960, "TOQUE NO LINK", 46, CREME, "ExtraBold")
    _centro(d, 1018, "AQUI EMBAIXO", 46, CREME, "ExtraBold")
    d.polygon([(L / 2 - 45, 1110), (L / 2 + 45, 1110), (L / 2, 1175)], fill=OURO)
    img.save(destino)


def gerar(origem: Path, destino: Path, chamada: str):
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(origem)]))
    with tempfile.TemporaryDirectory() as tmp:
        f_png, c_png = Path(tmp) / "faixa.png", Path(tmp) / "cartao.png"
        faixa(chamada, f_png)
        cartao(c_png)
        filtro = (
            f"[0:v]scale={L}:{A},setsar=1,tpad=stop_mode=clone:stop_duration={CARTAO_S}[v0];"
            f"[v0][1:v]overlay=0:0:enable='lt(t,{dur})'[v1];"
            f"[v1][2:v]overlay=0:0:enable='gte(t,{dur})'[v]"
        )
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(origem), "-loop", "1", "-i", str(f_png),
             "-loop", "1", "-i", str(c_png), "-filter_complex", filtro, "-map", "[v]", "-map", "0:a?",
             "-af", f"apad=pad_dur={CARTAO_S},afade=t=out:st={dur}:d={CARTAO_S}",
             "-t", f"{dur + CARTAO_S:.2f}", "-r", "30",
             "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(destino)],
            check=True)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    filtro_nome = sys.argv[1] if len(sys.argv) > 1 else ""
    videos = sorted(p for p in (RAIZ / "assets" / "ze").glob("ze_*.mp4") if filtro_nome in p.stem)
    legendas = []
    for i, v in enumerate(videos):
        destino = SAIDA / f"{v.stem}_whatsapp.mp4"
        gerar(v, destino, CHAMADAS[i % len(CHAMADAS)])
        legendas.append(f"## {destino.name}\n{LEGENDAS[i % len(LEGENDAS)].format(link=INSTAGRAM)}\n")
        print(f"🎬 {destino.name}")
    (SAIDA / "legendas.txt").write_text("\n".join(legendas), encoding="utf-8")
    print(f"📝 Legendas em {SAIDA / 'legendas.txt'}")


if __name__ == "__main__":
    main()
