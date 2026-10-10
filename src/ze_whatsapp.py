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


def faixa(chamada, destino, embaixo=None):
    img = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 70, L - 40, 150), radius=40, fill=ESCURO + (215,))
    _centro(d, 92, chamada, 34, OURO, "ExtraBold")
    if embaixo:   # quadro de baixo (Busca do Zé)
        d.rounded_rectangle((40, 1010, L - 40, 1190), radius=36, fill=ESCURO + (225,))
        for i, linha in enumerate(embaixo):
            _centro(d, 1032 + i * 52, linha, 35 if i == 0 else 32, OURO if i == 0 else CREME, "ExtraBold")
    img.save(destino)


def cartao_busca(destino):
    img = Image.new("RGBA", (L, A), ESCURO + (238,))
    d = ImageDraw.Draw(img)
    logo = Image.open(LOGO).convert("RGBA")
    logo = logo.resize((260, int(260 * logo.height / logo.width)))
    y = 150
    d.ellipse((L / 2 - 160, y + logo.height / 2 - 160, L / 2 + 160, y + logo.height / 2 + 160), fill=CREME)
    img.alpha_composite(logo, ((L - logo.width) // 2, y))
    _centro(d, 520, "TÁ PROCURANDO", 52, CREME, "ExtraBold")
    _centro(d, 585, "ALGUMA COISA?", 52, CREME, "ExtraBold")
    _centro(d, 690, "Manda no direct do Instagram", 36, CREME, "SemiBold")
    d.rounded_rectangle((90, 750, L - 90, 860), radius=55, fill=OURO)
    _centro(d, 770, ARROBA, 62, ESCURO, "ExtraBold")
    _centro(d, 900, "que o Zé garimpa pra você. É de graça!", 32, OURO, "SemiBold")
    _centro(d, 1000, "TOQUE NO LINK", 46, CREME, "ExtraBold")
    _centro(d, 1058, "AQUI EMBAIXO", 46, CREME, "ExtraBold")
    d.polygon([(L / 2 - 45, 1140), (L / 2 + 45, 1140), (L / 2, 1205)], fill=OURO)
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


def gerar(origem: Path, destino: Path, chamada: str, busca=False):
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(origem)]))
    with tempfile.TemporaryDirectory() as tmp:
        f_png, c_png = Path(tmp) / "faixa.png", Path(tmp) / "cartao.png"
        if busca:
            faixa("🔎 BUSCA DO ZÉ".replace("🔎 ", ""), f_png,
                  ["TÁ PROCURANDO ALGUMA COISA?", "Me conta que eu garimpo", "os melhores preços pra você!"])
            cartao_busca(c_png)
        else:
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


DIRECT = "https://ig.me/m/garimpovip4"   # abre a conversa no direct do Instagram
LEGENDAS_BUSCA = [
    "Oi, pessoal! 👋 Tá procurando alguma coisa pra casa, pro carro, pro pet ou um presente?\n"
    "Manda o que você procura no direct do Garimpo VIP que o Zé garimpa na Shopee as melhores opções "
    "(boa nota, muita venda e bom preço) e te responde. É de graça 😉\n👉 {direct}",
    "Sabe aquele produto que você quer mas não acha um bom? 🔎\n"
    "Manda pro Zé Garimpo no Instagram que ele procura pra você 👉 {direct}",
]


def busca():
    """Vídeo da Busca do Zé para grupos: junta chamada → pedidos → achei, com o cartão do direct."""
    pasta = RAIZ / "assets" / "ze" / "busca"
    partes = [pasta / f"busca_{n}.mp4" for n in ("chamada", "pedidos", "achei") if (pasta / f"busca_{n}.mp4").exists()]
    SAIDA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        junto = Path(tmp) / "busca.mp4"
        ent = sum((["-i", str(p)] for p in partes), [])
        n = len(partes)
        cc = "".join(f"[{i}:v]scale={L}:{A},setsar=1,fps=30[v{i}];[{i}:a]aresample=48000[a{i}];" for i in range(n))
        cc += "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ent, "-filter_complex", cc, "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-crf", "18", "-c:a", "aac", str(junto)], check=True)
        gerar(junto, SAIDA / "busca_do_ze_whatsapp.mp4", "", busca=True)
    for p in partes:   # versões curtas, uma por cena
        gerar(p, SAIDA / f"{p.stem}_whatsapp.mp4", "", busca=True)
    texto = "\n\n".join(l.format(direct=DIRECT) for l in LEGENDAS_BUSCA)
    (SAIDA / "legendas_busca.txt").write_text(texto, encoding="utf-8")
    print("🔎 Busca do Zé pronta em", SAIDA)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "busca":
        return busca()
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
