"""🎉 Marco de seguidores do Garimpo VIP (01/11/2026).

Quando o @garimpovip4 passa de um marco (150, 200, 250, 300, 400, 500, 750, 1.000...), o post do Zé
daquele dia (13:30, src/ze.py) vira a comemoração: Zé soltando fogos com "CHEGAMOS A N GARIMPEIROS!"
gravado na tela e a chamada da Busca do Zé (legenda com #BuscaDoZe, então quem comenta o que procura
recebe 3 achados no direct). Sai no Instagram, story, Facebook e YouTube como o post normal do Zé.

Cada marco sai uma vez só (data/marcos.json). O de 100 saiu à mão em 01/11/2026 (manuais/ze5.mp4).
Se o perfil pular dois marcos de uma vez, comemora só o maior.
Desligar: variável MARCOS=0.

Prévia: python -m src.marcos 150   → data/relatorios/marco_150.mp4
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

BRT = timezone(timedelta(hours=-3))
ARQ = config.RAIZ / "data" / "marcos.json"
VIDEO = config.RAIZ / "assets" / "ze" / "ze_fogos.mp4"
MUSICA = config.RAIZ / "assets" / "musicas" / "splash_and_fanfare.mp3"
LIGADO = os.getenv("MARCOS", "1") != "0"
MARCOS = [100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000, 2500, 3000, 4000, 5000,
          7500, 10000, 15000, 20000, 25000, 30000, 40000, 50000, 75000, 100000]


def _num(n):
    return f"{n:,}".replace(",", ".")


def comemorados():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8")).get("comemorados", {})
    except (OSError, ValueError):
        return {}


def seguidores():
    """Seguidores do @garimpovip4 agora (None se não deu para ler)."""
    from . import metricas
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not token:
        return None
    try:
        return metricas._get(token, "me", {"fields": "followers_count"}).get("followers_count")
    except Exception as e:
        print(f"::warning::Não li os seguidores para o marco ({e}).")
        return None


def marco_da_vez(total):
    """Maior marco já alcançado que ainda não foi comemorado e é maior que todos os comemorados."""
    if not total:
        return None
    feitos = [int(k) for k in comemorados()]
    acima = max(feitos, default=0)
    alcancados = [m for m in MARCOS if m <= total and m > acima]
    return max(alcancados) if alcancados else None


def gravar_video(n, saida):
    """Zé soltando fogos (8 s) com as duas frases na tela e fanfarra por baixo."""
    from .ze import _ffmpeg
    from .ze_textos import cartela
    saida = Path(saida)
    t0, t1 = saida.with_name(f"{saida.stem}_t0.png"), saida.with_name(f"{saida.stem}_t1.png")
    cartela(f"CHEGAMOS A {_num(n)} GARIMPEIROS! VALEU DEMAIS!", t0)
    cartela("COMENTA O QUE VOCÊ PROCURA QUE O ZÉ GARIMPA PRA VOCÊ", t1)
    filtro = ("[0:v]scale=1080:1920,setsar=1[v0];"
              "[v0][1:v]overlay=0:0:enable='between(t,0.3,4)'[v1];"
              "[v1][2:v]overlay=0:0:enable='between(t,4,8)',format=yuv420p[vf];"
              "[3:a]volume=0.5,atrim=0:8,afade=t=out:st=7:d=1[m];"
              "[0:a][m]amix=inputs=2:duration=first[a]")
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-i", str(VIDEO), "-i", str(t0), "-i", str(t1),
           "-i", str(MUSICA), "-filter_complex", filtro, "-map", "[vf]", "-map", "[a]", "-t", "8",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(saida)]
    try:
        subprocess.run(cmd, check=True)
    finally:
        t0.unlink(missing_ok=True)
        t1.unlink(missing_ok=True)


def legenda(n):
    return (f"🎉 Chegamos a {_num(n)} garimpeiros! Valeu demais por seguir o Zé. 🤠💛\n\n"
            "Pra comemorar: comenta aqui o que você tá procurando (ex.: \"fone bluetooth\", "
            "\"organizador de pia\") que o Zé garimpa e te manda 3 achados no direct.\n\n"
            "#BuscaDoZe #garimpovip #zegarimpo #achadinhos #achadinhosshopee")


def registrar(n, media_id=None):
    try:
        dados = json.loads(ARQ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {"comemorados": {}}
    dados.setdefault("comemorados", {})[str(n)] = {
        "em": datetime.now(BRT).strftime("%d/%m/%Y %H:%M"), "media_id": media_id}
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    pasta = config.RAIZ / "data" / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    gravar_video(n, pasta / f"marco_{n}.mp4")
    print(f"✅ Prévia: {pasta / f'marco_{n}.mp4'}")
