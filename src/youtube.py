"""YouTube Shorts: sobe os mesmos Reels do Instagram no canal do Garimpo VIP.

Segredos (o Fred cadastra no GitHub): YT_CLIENT_ID, YT_CLIENT_SECRET e YT_REFRESH_TOKEN
(OAuth do Google com os escopos youtube.upload E youtube.force-ssl, autorizado no canal Garimpo VIP;
sem o force-ssl o robô sobe Shorts mas não consegue ler nem responder comentários).

No Shorts o link da descrição não é clicável, então a descrição manda a pessoa para o
canal do Telegram (link clicável no perfil do canal), onde toda oferta tem o link.
"""
import json
import os
import re

import requests

from . import config

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
TELEGRAM = "t.me/garimpovipofertas"
CATEGORIA_YT = "26"   # "Guias e estilo" (Howto & Style)


def _env(n):
    return (os.getenv(n) or "").strip()


def configurado():
    return all(_env(n) for n in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def _token():
    r = requests.post(TOKEN_URL, timeout=30, data={
        "client_id": _env("YT_CLIENT_ID"), "client_secret": _env("YT_CLIENT_SECRET"),
        "refresh_token": _env("YT_REFRESH_TOKEN"), "grant_type": "refresh_token"})
    if r.status_code != 200:
        raise RuntimeError(f"Google não renovou o acesso (HTTP {r.status_code}): {' '.join(r.text.split())[:200]}")
    return r.json()["access_token"]


def _limpo(txt):
    return re.sub(r"[<>]", "", txt or "").strip()


def titulo(oferta):
    base = f"{oferta.get('titulo') or oferta['nome'][:60]} por R$ {oferta['preco_fmt']}"
    if oferta.get("nivel") == "achado":
        base = "💎 " + base
    return _limpo(base)[:90] + " #shorts"


def descricao(oferta):
    linhas = [l for l in (oferta.get("legenda") or "").splitlines()
              if l.strip() and "QUERO" not in l.upper() and not l.startswith("#")]
    tags = " ".join(t for t in (oferta.get("legenda") or "").split() if t.startswith("#"))
    corpo = "\n".join(linhas)
    return _limpo(
        f"{corpo}\n\n🔗 O link deste achado está no nosso canal do Telegram: {TELEGRAM}\n"
        f"(link clicável no perfil do canal)\n\n"
        f"Instagram: @{config.ARROBA}\n"
        f"Link de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA}.\n\n{tags} #shorts #achadinhos")[:4900]


def enviar_short(caminho_mp4, oferta):
    """Sobe o Reels da oferta como Short público e devolve o id do vídeo no YouTube."""
    return enviar_video(caminho_mp4, titulo(oferta), descricao(oferta),
                        ["achadinhos", "shopee", "achados", "ofertas", oferta.get("categoria", "")])


def enviar_video(caminho_mp4, titulo_yt, descricao_yt, tags):
    """Sobe qualquer vídeo vertical como Short público e devolve o id."""
    tok = _token()
    meta = {"snippet": {"title": _limpo(titulo_yt)[:100], "description": _limpo(descricao_yt)[:4900],
                        "categoryId": CATEGORIA_YT, "defaultLanguage": "pt-BR",
                        "tags": [t for t in tags if t]},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    dados = open(caminho_mp4, "rb").read()
    ini = requests.post(UPLOAD_URL, timeout=60, data=json.dumps(meta), headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(dados))})
    if ini.status_code != 200 or "Location" not in ini.headers:
        raise RuntimeError(f"YouTube recusou o envio (HTTP {ini.status_code}): {ini.text[:300]}")
    up = requests.put(ini.headers["Location"], data=dados, timeout=300,
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"})
    if up.status_code not in (200, 201):
        raise RuntimeError(f"Falha no envio do vídeo (HTTP {up.status_code}): {up.text[:300]}")
    return up.json().get("id")


CANAL_ID = os.getenv("YT_CHANNEL_ID", "UCVgPSlZGC3iydugIP81hl9Q")   # canal Garimpo VIP (@garimpoVIP4)
_tok_cache = {}


def _token_cache():
    if "t" not in _tok_cache:
        _tok_cache["t"] = _token()
    return _tok_cache["t"]


def comentarios_recentes(limite=50):
    """Comentários mais recentes de TODOS os vídeos do canal numa chamada só (1 unidade de cota).
    Devolve [{id, video, texto, autor, autor_canal}]."""
    r = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", timeout=30,
                     headers={"Authorization": f"Bearer {_token_cache()}"},
                     params={"part": "snippet", "allThreadsRelatedToChannelId": CANAL_ID,
                             "order": "time", "maxResults": limite, "textFormat": "plainText"})
    if r.status_code != 200:
        raise RuntimeError(f"YouTube comentários (HTTP {r.status_code}): {' '.join(r.text.split())[:200]}")
    saida = []
    for item in r.json().get("items", []):
        top = item["snippet"]["topLevelComment"]
        sn = top["snippet"]
        saida.append({"id": top["id"], "video": item["snippet"].get("videoId"),
                      "texto": sn.get("textOriginal") or sn.get("textDisplay") or "",
                      "autor": sn.get("authorDisplayName", ""),
                      "autor_canal": (sn.get("authorChannelId") or {}).get("value", "")})
    return saida


def responder_comentario(comment_id, texto):
    r = requests.post("https://www.googleapis.com/youtube/v3/comments", params={"part": "snippet"}, timeout=30,
                      headers={"Authorization": f"Bearer {_token_cache()}", "Content-Type": "application/json"},
                      data=json.dumps({"snippet": {"parentId": comment_id, "textOriginal": texto}}))
    if r.status_code not in (200, 201):
        raise RuntimeError(f"YouTube resposta (HTTP {r.status_code}): {' '.join(r.text.split())[:200]}")
    return r.json().get("id")


def apagar(video_id):
    tok = _token()
    r = requests.delete("https://www.googleapis.com/youtube/v3/videos", params={"id": video_id},
                        headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if r.status_code not in (204, 404):
        raise RuntimeError(f"YouTube não apagou {video_id} (HTTP {r.status_code}): {' '.join(r.text.split())[:200]}")


def enviar_oferta_da_fila(oferta_id=""):
    """Teste manual: gera o Reels de uma oferta já postada e sobe como Short (padrão: o último Reels)."""
    import tempfile
    from pathlib import Path
    from . import reels
    from .garimpar import carregar_fila, salvar_fila
    fila = carregar_fila()
    if oferta_id:
        oferta = fila["ofertas"][oferta_id]
    else:
        feitos = [o for o in fila["ofertas"].values()
                  if o.get("status") == "postado" and o.get("formato") == "reels" and not o.get("yt_video")]
        if not feitos:
            raise SystemExit("Nenhum Reels postado sem Short ainda.")
        oferta = max(feitos, key=lambda o: o.get("postado_em", ""))
    destino = Path(tempfile.mkdtemp()) / "short.mp4"
    reels.gerar(oferta, destino)
    vid = enviar_short(destino, oferta)
    oferta["yt_video"] = vid
    salvar_fila(fila)
    print(f"::notice::Short publicado: https://youtube.com/shorts/{vid} — {oferta.get('titulo')}")


if __name__ == "__main__":   # teste: python -m src.youtube  |  envio de teste: python -m src.youtube enviar [id]
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "enviar":
        try:
            enviar_oferta_da_fila(sys.argv[2] if len(sys.argv) > 2 else "")
        except Exception as e:
            print(f"::error::{e}")
            raise SystemExit(1)
        raise SystemExit(0)
    if not configurado():
        print("⏸️  YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN ainda não cadastrados.")
    else:
        try:
            tok = _token()
        except Exception as e:
            print(f"::error::{e}")
            raise SystemExit(1)
        r = requests.get("https://www.googleapis.com/youtube/v3/channels",
                         params={"part": "snippet,statistics", "mine": "true"},
                         headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        canais = r.json().get("items", [])
        if not canais:
            print(f"::error::Acesso ok, mas nenhum canal encontrado: {r.text[:300]}")
            raise SystemExit(1)
        c = canais[0]
        print(f"::notice::Canal: {c['snippet']['title']} — inscritos: "
              f"{c['statistics'].get('subscriberCount')} — vídeos: {c['statistics'].get('videoCount')}")
        try:
            n = len(comentarios_recentes(5))
            print(f"::notice::Comentários: acesso ok ({n} recentes lidos).")
        except Exception as e:
            print(f"::error::Sem permissão para comentários. Gere o YT_REFRESH_TOKEN de novo marcando também "
                  f"o escopo youtube.force-ssl. Detalhe: {e}")
            raise SystemExit(1)
