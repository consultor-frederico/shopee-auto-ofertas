"""Postagem no TikTok (@vipgarimpo4) pela Content Posting API, em Modo Foto (31/10/2026).

DESLIGADO até o Fred cadastrar os segredos TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET e TIKTOK_REFRESH_TOKEN
(o último sai do workflow 25 "Conectar TikTok"). Sem eles nada aqui roda e o kit no Telegram segue igual.

Dois modos (variável do repositório TIKTOK_MODO):
  rascunho (padrão) → MEDIA_UPLOAD: as fotos chegam na caixa de entrada do app do TikTok do Fred, que abre a
                      notificação, escolhe a música em alta e posta. Não depende da auditoria.
  direto            → DIRECT_POST com música automática. Enquanto o app não passar na auditoria do TikTok o
                      post sai PRIVADO (SELF_ONLY) e só 5 contas podem usar o app por dia.
As fotos precisam estar num endereço verificado no app do TikTok ("URL properties"):
https://consultor-frederico.github.io/shopee-auto-ofertas/ (o arquivo de verificação vai em assets/paginas).

Uso:
  python -m src.tiktok conectar            → sem TIKTOK_CODIGO: imprime o link de autorização
                                             com TIKTOK_CODIGO: troca o código pelo refresh token
  python -m src.tiktok status              → confere o token e mostra a conta conectada
"""
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote

import requests

API = "https://open.tiktokapis.com/v2"
REDIRECT = "https://garimpovipbr.github.io/tiktok.html"   # página pública sem o nome do Fred
ESCOPOS = "user.info.basic,video.publish,video.upload"
ARQ_NOVO_TOKEN = Path(os.getenv("RUNNER_TEMP", "/tmp")) / "tiktok_refresh.txt"


def _env(nome):
    return os.getenv(nome, "").strip()


def ligado():
    return all(_env(n) for n in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"))


def modo():
    return "direto" if _env("TIKTOK_MODO").lower() == "direto" else "rascunho"


def _token(dados):
    r = requests.post(f"{API}/oauth/token/", timeout=30, data={
        "client_key": _env("TIKTOK_CLIENT_KEY"), "client_secret": _env("TIKTOK_CLIENT_SECRET"), **dados},
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"TikTok recusou o token: {j.get('error')} {j.get('error_description')}")
    novo = j.get("refresh_token")
    if novo and novo != _env("TIKTOK_REFRESH_TOKEN"):   # o workflow salva no segredo com o GH_PAT
        ARQ_NOVO_TOKEN.write_text(novo)
    return j


def access_token():
    return _token({"grant_type": "refresh_token", "refresh_token": _env("TIKTOK_REFRESH_TOKEN")})["access_token"]


def _post(caminho, tok, corpo):
    r = requests.post(f"{API}{caminho}", json=corpo, timeout=60,
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"})
    j = r.json()
    err = j.get("error") or {}
    if err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok {caminho}: {err.get('code')} {err.get('message')}")
    return j.get("data") or {}


def postar_fotos(urls, titulo, descricao):
    """Manda até 35 fotos (URLs públicas e verificadas). Devolve (publish_id, situação final)."""
    tok = access_token()
    if modo() == "direto":
        info = _post("/post/publish/creator_info/query/", tok, {})
        opcoes = info.get("privacy_level_options") or ["SELF_ONLY"]
        privacidade = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in opcoes else "SELF_ONLY"
        post_info = {"title": titulo[:90], "description": descricao[:4000], "privacy_level": privacidade,
                     "disable_comment": False, "auto_add_music": True}
        post_mode = "DIRECT_POST"
    else:
        post_info = {"title": titulo[:90], "description": descricao[:4000]}
        post_mode = "MEDIA_UPLOAD"
    dados = _post("/post/publish/content/init/", tok, {
        "post_info": post_info, "post_mode": post_mode, "media_type": "PHOTO",
        "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0, "photo_images": list(urls)[:35]}})
    pid = dados.get("publish_id")
    situacao = "?"
    for _ in range(20):   # o TikTok baixa as fotos e processa: até ~2 min
        time.sleep(6)
        situacao = _post("/post/publish/status/fetch/", tok, {"publish_id": pid}).get("status", "?")
        if situacao in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX", "FAILED"):
            break
    if situacao == "FAILED":
        raise RuntimeError(f"TikTok não processou as fotos (publish_id {pid}).")
    return pid, situacao


def _conectar():
    codigo = unquote(_env("TIKTOK_CODIGO"))
    if not _env("TIKTOK_CLIENT_KEY"):
        sys.exit("Falta o segredo TIKTOK_CLIENT_KEY.")
    if not codigo:
        link = (f"https://www.tiktok.com/v2/auth/authorize/?client_key={_env('TIKTOK_CLIENT_KEY')}"
                f"&scope={ESCOPOS}&response_type=code&redirect_uri={quote(REDIRECT, safe='')}&state=garimpo")
        print("1) Abra este link no navegador logado no TikTok @vipgarimpo4 e autorize:")
        print(link)
        print("2) A página que abre mostra um código. Rode este workflow de novo colando o código (vale ~5 min).")
        return
    j = _token({"grant_type": "authorization_code", "code": codigo, "redirect_uri": REDIRECT})
    ARQ_NOVO_TOKEN.write_text(j["refresh_token"])
    print(f"✅ Conectado (escopos: {j.get('scope')}). O refresh token vai ser salvo no segredo TIKTOK_REFRESH_TOKEN.")


def _status():
    u = _post("/post/publish/creator_info/query/", access_token(), {})
    print(f"✅ Token ok. Conta: {u.get('creator_nickname')} (@{u.get('creator_username')}). Modo: {modo()}. "
          f"Privacidade liberada: {u.get('privacy_level_options')}")
    if u.get("creator_username") and u["creator_username"] != "vipgarimpo4":
        sys.exit("⚠️  A conta conectada não é a @vipgarimpo4. Refaça o workflow 25 logado na conta certa.")

def _teste():
    """Manda 3 imagens do site da bio (prefixo verificado) como rascunho, para ver a notificação chegar no app."""
    urls = [f"https://garimpovipbr.github.io/{n}" for n in ("og-ze.jpg", "og.jpg", "ze.jpg")]
    pid, situacao = postar_fotos(urls, "Teste do Garimpo VIP 🤠⛏️",
                                 "Teste do robô do Garimpo VIP. Pode apagar este rascunho.")
    print(f"✅ Enviado ({modo()}): {situacao} (publish_id {pid}). Olhe as notificações do TikTok.")


if __name__ == "__main__":
    {"conectar": _conectar, "status": _status, "teste": _teste}[sys.argv[1] if len(sys.argv) > 1 else "status"]()
