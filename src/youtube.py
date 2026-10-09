"""YouTube Shorts: sobe os mesmos Reels do Instagram no canal do Garimpo VIP.

Segredos (o Fred cadastra no GitHub): YT_CLIENT_ID, YT_CLIENT_SECRET e YT_REFRESH_TOKEN
(OAuth do Google com o escopo youtube.upload, autorizado no canal Garimpo VIP).

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
        raise RuntimeError(f"Google não renovou o acesso (HTTP {r.status_code}): {r.text[:200]}")
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
    """Sobe o vídeo como público e devolve o id do vídeo no YouTube."""
    tok = _token()
    meta = {"snippet": {"title": titulo(oferta), "description": descricao(oferta),
                        "categoryId": CATEGORIA_YT, "defaultLanguage": "pt-BR",
                        "tags": ["achadinhos", "shopee", "achados", "ofertas", oferta.get("categoria", "")]},
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


def apagar(video_id):
    tok = _token()
    r = requests.delete("https://www.googleapis.com/youtube/v3/videos", params={"id": video_id},
                        headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if r.status_code not in (204, 404):
        raise RuntimeError(f"YouTube não apagou {video_id} (HTTP {r.status_code}): {r.text[:200]}")


if __name__ == "__main__":   # teste: python -m src.youtube
    if not configurado():
        print("⏸️  YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN ainda não cadastrados.")
    else:
        tok = _token()
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
