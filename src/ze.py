"""Zé Garimpo, o mascote do Garimpo VIP.

1) Final dos Reels: cada Reels de oferta ganha, no fim, uma vinheta curtinha do Zé
   (assets/ze/finais/*.mp4). O robô alterna entre elas, sem repetir a do post anterior.
   O Reels inteiro ganha uma das músicas de assets/musicas/, estendida até o fim do vídeo
   e mais baixa quando o Zé fala.
2) Post do Zé de 15 em 15 dias: um filminho de assets/ze/ze_*.mp4 vira Reels (Instagram,
   story, página do Facebook e YouTube Shorts). Vídeo novo que ainda não saiu vai primeiro;
   depois o robô repete o que está há mais tempo sem sair. O post é apagado depois de 15 dias
   (src/limpeza.py), junto com as ofertas.

  python -m src.ze preparar   → se já deu 15 dias, copia o vídeo da vez para site/
  python -m src.ze publicar   → publica e registra em data/ze.json
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

from . import config

PASTA = config.RAIZ / "assets" / "ze"
PASTA_FINAIS = PASTA / "finais"
ARQ = config.PASTA_DADOS / "ze.json"
ARQ_PROX = config.PASTA_DADOS / "proximo_ze.json"
PASTA_SITE = config.RAIZ / "site"
INTERVALO_DIAS = int(os.getenv("ZE_INTERVALO_DIAS", "15"))
FINAL_LIGADO = os.getenv("ZE_NO_FINAL", "1") != "0"
PASTA_MUSICAS = config.RAIZ / "assets" / "musicas"
MUSICA_LIGADA = os.getenv("MUSICA_REELS", "1") != "0"
VOLUME_MUSICA = float(os.getenv("VOLUME_MUSICA", "0.6"))

LEGENDAS = [
    "⛏️ O Zé Garimpo não para! Todo dia ele cava a Shopee e o AliExpress atrás dos achados "
    "que valem a pena, para você não cair em furada. 💎\n\n"
    "👉 Segue a página e ativa o sininho para não perder o próximo achado!",
    "🤠 Quem tem o Zé Garimpo do lado não paga caro! Ele confere preço, nota e vendas antes "
    "de mostrar qualquer produto. ✨\n\n"
    "💬 Conta aqui: o que você quer que o Zé garimpe pra você?",
    "💰 Achadinho bom é achadinho garimpado! O Zé passa o dia peneirando ofertas e só "
    "traz o que vale ouro. 🏆\n\n"
    "📣 Ofertas o dia todo, com link direto, no nosso canal do Telegram (link na bio)!",
    "✨ Mais um dia de garimpo! O Zé Garimpo encontra os achados e você só escolhe. 🛒\n\n"
    "👉 Marca aqui aquele amigo que ama um achadinho!",
]
HASHTAGS = "#zegarimpo #garimpovip #achadinhos #shopee #achados #ofertas #promoção"


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _carregar():
    if ARQ.exists():
        return json.loads(ARQ.read_text(encoding="utf-8"))
    return {"posts": [], "ultimo_final": ""}


def _salvar(dados):
    ARQ.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _agora():
    from .garimpar import agora
    return agora()


# ------------------------------------------------------------------ vinheta no fim dos Reels
def escolher_final(oferta=None):
    """Vinheta da vez: alterna pela oferta e nunca repete a última usada."""
    finais = sorted(PASTA_FINAIS.glob("*.mp4"))
    if not finais:
        return None
    dados = _carregar()
    ultimo = dados.get("ultimo_final", "")
    opcoes = [f for f in finais if f.name != ultimo] or finais
    semente = sum(map(ord, str((oferta or {}).get("id", time.time()))))
    escolhido = opcoes[semente % len(opcoes)]
    dados["ultimo_final"] = escolhido.name
    _salvar(dados)
    return escolhido


def _duracao(arquivo):
    r = subprocess.run([_ffmpeg(), "-hide_banner", "-i", str(arquivo)], capture_output=True, text=True)
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def escolher_musica(oferta=None):
    """Trilha da vez (assets/musicas/), alternando pela oferta."""
    musicas = sorted(PASTA_MUSICAS.glob("*.mp3"))
    if not musicas:
        return None
    semente = sum((i + 7) * ord(c) for i, c in enumerate(str((oferta or {}).get("id", time.time()))))
    return musicas[semente % len(musicas)]


def _com_musica(video, musica, saida):
    """Estende a música (emenda nela mesma com transição suave) até o fim do vídeo e
    abaixa o volume sempre que há voz no vídeo (o Zé falando, ou o áudio do vídeo manual)."""
    total = _duracao(video)
    voltas = max(1, int(total // max(1.0, _duracao(musica) - 1.0)) + 1)
    entradas = ["-i", str(video)] + ["-i", str(musica)] * voltas
    cadeia, ult = "", "[1:a]"
    for i in range(2, voltas + 1):
        cadeia += f"{ult}[{i}:a]acrossfade=d=1:c1=tri:c2=tri[m{i}];"
        ult = f"[m{i}]"
    filtro = (f"{cadeia}{ult}aresample=44100,aformat=channel_layouts=stereo,atrim=0:{total:.2f},"
              f"volume={VOLUME_MUSICA},afade=t=out:st={max(0, total - 0.8):.2f}:d=0.8[m];"
              "[0:a]aresample=44100,aformat=channel_layouts=stereo,asplit[v][k];"
              "[m][k]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[md];"
              "[v][md]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]")
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", *entradas, "-filter_complex", filtro,
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(saida)]
    subprocess.run(cmd, check=True)


def emendar_final(reels, oferta=None):
    """Cola a vinheta do Zé no fim do Reels e põe música no Reels inteiro (mesmo arquivo).
    Só no Garimpo VIP. Devolve o nome da vinheta usada."""
    if config.PERFIL != "garimpo":
        return None
    final = escolher_final(oferta) if FINAL_LIGADO else None
    if final:
        saida = reels.with_suffix(".com-ze.mp4")
        filtro = ("[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
                  "setsar=1,fps=30,format=yuv420p[v0];"
                  "[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
                  "setsar=1,fps=30,format=yuv420p[v1];"
                  "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];"
                  "[1:a]aresample=44100,aformat=channel_layouts=stereo[a1];"
                  "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
        cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-i", str(reels), "-i", str(final),
               "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(saida)]
        subprocess.run(cmd, check=True)
        saida.replace(reels)
        print(f"🤠 Vinheta do Zé no final do Reels: {final.name}")
    musica = escolher_musica(oferta) if MUSICA_LIGADA else None
    if musica:
        try:
            saida = reels.with_suffix(".com-musica.mp4")
            _com_musica(reels, musica, saida)
            saida.replace(reels)
            if oferta is not None:
                oferta["musica"] = musica.name
            print(f"🎵 Música no Reels: {musica.name}")
        except Exception as e:
            print(f"::warning::Música não entrou ({e}); o Reels sai sem ela.")
    return final.name if final else None


# ------------------------------------------------------------------ post do Zé (15 em 15 dias)
def videos():
    return sorted(PASTA.glob("ze_*.mp4"))


def video_da_vez(dados):
    """Primeiro os que nunca saíram; depois o que está há mais tempo sem sair."""
    ultimo_uso = {}
    for p in dados["posts"]:
        ultimo_uso[p["video"]] = max(ultimo_uso.get(p["video"], ""), p["postado_em"])
    lista = videos()
    if not lista:
        return None
    novos = [v for v in lista if v.name not in ultimo_uso]
    if novos:
        return novos[0]
    return min(lista, key=lambda v: ultimo_uso[v.name])


def dias_desde_ultimo(dados):
    from .garimpar import BRT, FMT
    if not dados["posts"]:
        return None
    ult = max(p["postado_em"] for p in dados["posts"])
    return (_agora() - datetime.strptime(ult, FMT).replace(tzinfo=BRT)).days


def _saida(chave, valor):
    arq = os.getenv("GITHUB_OUTPUT")
    if arq:
        with open(arq, "a") as f:
            f.write(f"{chave}={valor}\n")


def preparar():
    from . import instagram
    _saida("tem_post", "false")
    if config.PERFIL != "garimpo":
        print("⏸️  O Zé Garimpo é só do Garimpo VIP.")
        return
    if not instagram.tem_token():
        print("⏸️  IG_ACCESS_TOKEN ausente.")
        return
    dados = _carregar()
    dias = dias_desde_ultimo(dados)
    forcar = os.getenv("FORCAR") == "1"
    if dias is not None and dias < INTERVALO_DIAS and not forcar:
        print(f"⏳ Último post do Zé foi há {dias} dias — o próximo sai com {INTERVALO_DIAS}.")
        return
    video = video_da_vez(dados)
    if not video:
        print("⚠️  Nenhum vídeo ze_*.mp4 em assets/ze/.")
        return
    pasta = PASTA_SITE / "midia"
    pasta.mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    for fixo in (config.RAIZ / "assets" / "paginas").glob("*.html"):
        (PASTA_SITE / fixo.name).write_text(fixo.read_text(encoding="utf-8"), encoding="utf-8")
    nome = f"ze-{int(time.time())}.mp4"
    shutil.copy(video, pasta / nome)
    n = len(dados["posts"])
    leg = LEGENDAS[n % len(LEGENDAS)] + "\n\n" + HASHTAGS
    ARQ_PROX.write_text(json.dumps({"arquivo": f"midia/{nome}", "video": video.name, "legenda": leg},
                                   ensure_ascii=False), encoding="utf-8")
    print(f"🎬 Post do Zé preparado: {video.name}")
    _saida("tem_post", "true")


def publicar():
    from . import facebook, instagram, youtube
    from .garimpar import FMT
    from .postar import _esperar_url, legenda_facebook
    prox = json.loads(ARQ_PROX.read_text(encoding="utf-8"))
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    url = f"{base}/{prox['arquivo']}"
    _esperar_url(url)
    ig_id = instagram.conferir_conta()["user_id"]
    cont = instagram.criar_container(ig_id, prox["legenda"], video_url=url)
    instagram.aguardar_container(cont)
    media = instagram.publicar(ig_id, cont)
    reg = {"video": prox["video"], "postado_em": _agora().strftime(FMT), "id_post": media,
           "permalink": instagram.permalink(media), "status": "postado"}
    dados = _carregar()
    dados["posts"].append(reg)
    _salvar(dados)
    ARQ_PROX.unlink(missing_ok=True)
    print(f"✅ Zé publicado no Instagram: {reg['permalink'] or media}")
    try:
        cs = instagram.criar_story(ig_id, video_url=url)
        instagram.aguardar_container(cs)
        instagram.publicar(ig_id, cs)
        print("📲 Também no story.")
    except Exception as e:
        print(f"::warning::Story do Zé falhou: {e}")
    if facebook.configurado():
        try:
            reg["fb_post"] = facebook.postar_video(url, legenda_facebook(prox["legenda"]))
            print(f"📘 Zé na página do Facebook ({reg['fb_post']}).")
        except Exception as e:
            print(f"::warning::Facebook falhou: {e}")
    if youtube.configurado():
        try:
            corpo = prox["legenda"].split("\n\n#")[0]
            reg["yt_video"] = youtube.enviar_video(
                PASTA_SITE / prox["arquivo"], "Zé Garimpo achando ofertas pra você! ⛏️ #shorts",
                f"{corpo}\n\n📣 Ofertas com link direto no Telegram: {youtube.TELEGRAM}\n\n{HASHTAGS} #shorts",
                ["zé garimpo", "achadinhos", "shopee", "ofertas"])
            print(f"▶️  Zé no YouTube Shorts: https://youtube.com/shorts/{reg['yt_video']}")
        except Exception as e:
            print(f"::warning::YouTube falhou: {e}")
    _salvar(dados)


if __name__ == "__main__":
    acao = {"preparar": preparar, "publicar": publicar}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if not acao:
        print("Uso: python -m src.ze preparar|publicar")
        sys.exit(2)
    try:
        acao()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
