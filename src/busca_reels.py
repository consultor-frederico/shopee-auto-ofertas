"""🔎 Rodízio da Busca do Zé: uma vez por semana, um Reels animado da Busca vai para o Instagram.

- Vídeos em assets/ze/busca/busca_*.mp4 (os vídeos do Flow, 9:16). O robô alterna entre eles:
  o que nunca saiu vai primeiro; depois o que está há mais tempo sem sair.
- Como quase ninguém lê legenda, o robô grava a chamada POR CIMA do vídeo, do começo ao fim:
  faixa "BUSCA DO ZÉ" no alto e o quadro "TÁ PROCURANDO ALGUMA COISA? Comenta aqui..." embaixo.
- Legenda com #BuscaDoZe: assim a busca (src/busca_ze.py) funciona nos comentários desse Reels.
- Quando sai um Reels novo da Busca, o anterior é apagado (o post fixo com a foto fica sempre).
- Ganha uma das músicas de assets/musicas/ por baixo da voz do Zé (igual aos outros Reels).
- Só no Instagram (+ story): é lá que a busca responde no direct.

  python -m src.busca_reels preparar   → se já deu o intervalo, monta o vídeo em site/
  python -m src.busca_reels publicar   → publica, apaga o Reels anterior e registra
  python -m src.busca_reels previa ARQ → só grava a faixa num vídeo (para conferir)
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

PASTA = config.RAIZ / "assets" / "ze" / "busca"
ARQ = config.PASTA_DADOS / "busca_reels.json"
ARQ_PROX = config.PASTA_DADOS / "proxima_busca.json"
PASTA_SITE = config.RAIZ / "site"
INTERVALO_DIAS = int(os.getenv("BUSCA_INTERVALO_DIAS", "7"))
W, H = 1080, 1920

LEGENDAS = [
    "🔎 BUSCA DO ZÉ ⛏️\n\nTá procurando alguma coisa na Shopee? Comenta aqui embaixo o que você quer "
    "(ex.: \"fone bluetooth\", \"organizador de cozinha\") e o Zé te manda no direct os 3 melhores achados! 🤠\n\n🤫 Prefere não comentar? Manda no direct o que você procura que funciona igual!",
    "🔎 BUSCA DO ZÉ ⛏️\n\nDeixa o Zé garimpar pra você! Escreve nos comentários o produto que você procura "
    "e em poucos minutos chegam no seu direct os achados com nota alta e muita venda. 💎\n\n📩 Também dá pra pedir direto no direct da página!",
    "🔎 BUSCA DO ZÉ ⛏️\n\nNão achou o que queria no feed? Comenta aqui o que você procura que o Zé cava "
    "na Shopee e te manda os melhores no direct. Pode pedir quantas vezes quiser! 🤠\n\n📩 Se preferir, manda o pedido no direct que o Zé responde lá mesmo.",
]
HASHTAGS = "#BuscaDoZe #garimpovip #zegarimpo #achadinhos #shopee #achados #ofertas"

ESCURO = "#24150A"
DOURADO = "#E2BE68"
DOURADO_ESC = "#A07E30"


def _agora():
    from .garimpar import agora
    return agora()


def _carregar():
    if ARQ.exists():
        return json.loads(ARQ.read_text(encoding="utf-8"))
    return {"posts": []}


def _salvar(d):
    ARQ.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _fonte(tam, peso="ExtraBold"):
    f = ImageFont.truetype(str(config.FONTE), tam)
    try:
        f.set_variation_by_name(peso)
    except Exception:
        pass
    return f


def _centro(d, y, txt, fonte, cor, w=W):
    larg = d.textlength(txt, font=fonte)
    d.text(((w - larg) / 2, y), txt, font=fonte, fill=cor)


def _lupa(d, cx, cy, r, cor, esp):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=cor, width=esp)
    d.line([cx + r * 0.7, cy + r * 0.7, cx + r * 1.6, cy + r * 1.6], fill=cor, width=esp + 4)


def faixa(destino):
    """PNG transparente 1080x1920 com a chamada da busca. Tudo fica entre y=300 e y=1600: aparece inteiro
    no Reels em tela cheia, no feed (corte 4:5) e na grade do perfil (corte 3:4)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # alto: selo "BUSCA DO ZÉ"
    f1 = _fonte(64)
    txt = "BUSCA DO ZÉ"
    tl = d.textlength(txt, font=f1)
    pw, ph = tl + 190, 120
    x0, y0 = (W - pw) / 2, 330
    d.rounded_rectangle([x0 + 6, y0 + 8, x0 + pw + 6, y0 + ph + 8], ph // 2, fill=(0, 0, 0, 110))
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], ph // 2, fill=ESCURO, outline=DOURADO, width=6)
    _lupa(d, x0 + 70, y0 + ph / 2 - 8, 22, DOURADO, 8)
    d.text((x0 + 130, y0 + (ph - 64) / 2 - 6), txt, font=f1, fill=DOURADO)
    # embaixo: quadro com a pergunta (acima da legenda e longe dos ícones da direita)
    bx0, bx1, by0, by1 = 70, 930, 1220, 1490
    d.rounded_rectangle([bx0 + 8, by0 + 10, bx1 + 8, by1 + 10], 44, fill=(0, 0, 0, 120))
    d.rounded_rectangle([bx0, by0, bx1, by1], 44, fill=DOURADO, outline=ESCURO, width=7)
    bw = bx1 - bx0
    camada = Image.new("RGBA", (bw, by1 - by0), (0, 0, 0, 0))
    dc = ImageDraw.Draw(camada)
    _centro(dc, 38, "TÁ PROCURANDO", _fonte(68), ESCURO, bw)
    _centro(dc, 112, "ALGUMA COISA?", _fonte(68), ESCURO, bw)
    _centro(dc, 200, "Comenta aqui que o Zé acha pra você", _fonte(37, "SemiBold"), ESCURO, bw)
    img.alpha_composite(camada, (bx0, by0))
    # seta para os comentários
    cx, ay = (bx0 + bx1) / 2, by1 + 22
    d.polygon([(cx - 60, ay), (cx + 60, ay), (cx, ay + 75)], fill=DOURADO, outline=ESCURO, width=6)
    img.save(destino)
    return destino


def gravar_faixa(video, saida):
    """Ajusta o vídeo para 1080x1920 e grava a faixa por cima do começo ao fim (mantém o áudio)."""
    from .ze import _ffmpeg
    png = Path(saida).with_suffix(".png")
    faixa(png)
    filtro = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v];[v][1:v]overlay=0:0,format=yuv420p")
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-i", str(video), "-i", str(png),
           "-filter_complex", filtro, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(saida)]
    subprocess.run(cmd, check=True)
    png.unlink(missing_ok=True)
    return _musica(video, saida)


def _musica(video, saida):
    """Música das outras postagens do Zé (assets/musicas/) por baixo da voz, que abaixa quando ele fala."""
    from .ze import MUSICA_LIGADA, _com_musica, escolher_musica
    musica = escolher_musica({"id": Path(video).name}) if MUSICA_LIGADA else None
    if not musica:
        return saida
    tmp = Path(saida).with_name(Path(saida).stem + "_m.mp4")
    try:
        _com_musica(saida, musica, tmp)
        tmp.replace(saida)
        print(f"🎵 Música: {musica.name}")
    except Exception as e:
        tmp.unlink(missing_ok=True)
        print(f"::warning::Música não entrou ({e}); o Reels sai sem ela.")
    return saida


def videos():
    return sorted(PASTA.glob("busca_*.mp4"))


def video_da_vez(d):
    uso = {}
    for p in d["posts"]:
        uso[p["video"]] = max(uso.get(p["video"], ""), p["postado_em"])
    lista = videos()
    if not lista:
        return None
    novos = [v for v in lista if v.name not in uso]
    return novos[0] if novos else min(lista, key=lambda v: uso[v.name])


def dias_desde_ultimo(d):
    from .garimpar import BRT, FMT
    if not d["posts"]:
        return None
    ult = max(p["postado_em"] for p in d["posts"])
    # conta dias de calendário: postado sábado às 15h, o próximo sai no sábado seguinte às 11h30
    return (_agora().date() - datetime.strptime(ult, FMT).replace(tzinfo=BRT).date()).days


def preparar():
    from . import instagram
    from .ze import _saida
    _saida("tem_post", "false")
    if config.PERFIL != "garimpo":
        print("⏸️  A Busca do Zé é só do Garimpo VIP.")
        return
    if not instagram.tem_token():
        print("⏸️  IG_ACCESS_TOKEN ausente.")
        return
    d = _carregar()
    dias = dias_desde_ultimo(d)
    if os.getenv("FORCAR") != "1" and dias is not None and dias < INTERVALO_DIAS:
        print(f"⏳ Último Reels da Busca saiu há {dias} dias; o próximo sai com {INTERVALO_DIAS}.")
        return
    video = video_da_vez(d)
    if not video:
        print("⚠️  Nenhum vídeo busca_*.mp4 em assets/ze/busca/ — mande os vídeos da Busca do Zé.")
        return
    pasta = PASTA_SITE / "midia"
    pasta.mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    for fixo in (config.RAIZ / "assets" / "paginas").glob("*.html"):
        (PASTA_SITE / fixo.name).write_text(fixo.read_text(encoding="utf-8"), encoding="utf-8")
    nome = f"busca-{int(time.time())}.mp4"
    gravar_faixa(video, pasta / nome)
    leg = LEGENDAS[len(d["posts"]) % len(LEGENDAS)] + "\n\n" + HASHTAGS
    ARQ_PROX.write_text(json.dumps({"arquivo": f"midia/{nome}", "video": video.name, "legenda": leg},
                                   ensure_ascii=False), encoding="utf-8")
    print(f"🎬 Reels da Busca preparado: {video.name}")
    _saida("tem_post", "true")


def publicar():
    from . import facebook, instagram
    from .garimpar import FMT
    from .postar import _esperar_url
    prox = json.loads(ARQ_PROX.read_text(encoding="utf-8"))
    url = f"{(os.getenv('PAGES_URL') or '').rstrip('/')}/{prox['arquivo']}"
    _esperar_url(url)
    ig_id = instagram.conferir_conta()["user_id"]
    cont = instagram.criar_container(ig_id, prox["legenda"], video_url=url)
    instagram.aguardar_container(cont)
    media = instagram.publicar(ig_id, cont)
    d = _carregar()
    anteriores = [p for p in d["posts"] if p.get("status") == "postado"]
    d["posts"].append({"video": prox["video"], "postado_em": _agora().strftime(FMT), "id_post": media,
                       "permalink": instagram.permalink(media), "status": "postado"})
    _salvar(d)
    ARQ_PROX.unlink(missing_ok=True)
    print(f"✅ Reels da Busca do Zé publicado: {d['posts'][-1]['permalink'] or media}")
    try:
        cs = instagram.criar_story(ig_id, video_url=url)
        instagram.aguardar_container(cs)
        instagram.publicar(ig_id, cs)
        print("📲 Também no story.")
    except Exception as e:
        print(f"::warning::Story da Busca falhou: {e}")
    if anteriores and facebook.configurado():   # o Reels anterior da Busca sai do perfil
        for p in anteriores:
            try:
                facebook.apagar(p["id_post"])
                p["status"] = "apagado"
                print(f"🗑️  Reels anterior da Busca apagado ({p['video']}).")
            except Exception as e:
                print(f"::warning::Não apaguei o Reels anterior da Busca: {e}")
        _salvar(d)


def previa(arquivo):
    saida = Path(arquivo).with_name(Path(arquivo).stem + "_previa.mp4")
    gravar_faixa(arquivo, saida)
    print(f"✅ Prévia: {saida}")


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if acao == "preparar":
            preparar()
        elif acao == "publicar":
            publicar()
        elif acao == "previa" and len(sys.argv) > 2:
            previa(sys.argv[2])
        else:
            print("Uso: python -m src.busca_reels preparar|publicar|previa ARQUIVO")
            sys.exit(2)
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
