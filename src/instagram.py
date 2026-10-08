"""Cliente da API do Instagram (login do Instagram, host graph.instagram.com)."""
import os
import time

import requests

VERSAO = os.getenv("IG_API_VERSION", "v23.0")
API = f"https://graph.instagram.com/{VERSAO}"


class ErroInstagram(RuntimeError):
    pass


def token():
    t = (os.getenv("IG_ACCESS_TOKEN") or "").strip()
    if not t:
        raise ErroInstagram("Segredo IG_ACCESS_TOKEN não configurado.")
    return t


def tem_token():
    return bool((os.getenv("IG_ACCESS_TOKEN") or "").strip())


def _req(metodo, caminho, params=None, json=None, url=None):
    r = requests.request(metodo, url or f"{API}/{caminho}", params=params, json=json, timeout=60,
                         headers={"Authorization": f"Bearer {token()}"})
    try:
        corpo = r.json()
    except ValueError:
        raise ErroInstagram(f"HTTP {r.status_code}: {r.text[:300]}")
    if r.status_code >= 400 or "error" in corpo:
        erro = corpo.get("error", corpo)
        raise ErroInstagram(f"HTTP {r.status_code}: {erro.get('message', erro)} "
                            f"(code {erro.get('code')}, subcode {erro.get('error_subcode')})")
    return corpo


def conta():
    """Retorna {'user_id': id da conta profissional, 'username': ...}."""
    c = _req("GET", "me", params={"fields": "user_id,username"})
    c["user_id"] = str(c.get("user_id") or c.get("id"))
    return c


def criar_container(ig_id, legenda, imagem_url=None, video_url=None):
    if video_url:
        params = {"media_type": "REELS", "video_url": video_url, "caption": legenda,
                  "share_to_feed": "true"}
    else:
        params = {"image_url": imagem_url, "caption": legenda}
    return _req("POST", f"{ig_id}/media", params=params)["id"]


def aguardar_container(container_id, limite_s=600):
    inicio = time.time()
    while time.time() - inicio < limite_s:
        st = _req("GET", container_id, params={"fields": "status_code,status"})
        codigo = st.get("status_code")
        if codigo in ("FINISHED", "PUBLISHED"):
            return
        if codigo in ("ERROR", "EXPIRED"):
            raise ErroInstagram(f"Container {codigo}: {st.get('status')}")
        time.sleep(10)
    raise ErroInstagram("Tempo esgotado esperando o Instagram processar a mídia.")


def publicar(ig_id, container_id):
    return _req("POST", f"{ig_id}/media_publish", params={"creation_id": container_id})["id"]


def permalink(media_id):
    try:
        return _req("GET", media_id, params={"fields": "permalink"}).get("permalink", "")
    except ErroInstagram:
        return ""


def comentarios(media_id):
    """Todos os comentários de um post (com paginação)."""
    itens, url, params = [], None, {"fields": "id,text,timestamp,username,from", "limit": 50}
    caminho = f"{media_id}/comments"
    while True:
        corpo = _req("GET", caminho, params=params, url=url)
        itens += corpo.get("data", [])
        url = (corpo.get("paging") or {}).get("next")
        if not url:
            return itens
        params = None


def resposta_privada(ig_id, comment_id, texto):
    return _req("POST", f"{ig_id}/messages",
                json={"recipient": {"comment_id": comment_id}, "message": {"text": texto}})


def responder_comentario(comment_id, texto):
    return _req("POST", f"{comment_id}/replies", params={"message": texto})


def renovar_token():
    """Renova o token de longa duração (precisa ter mais de 24h e não estar vencido)."""
    r = requests.get("https://graph.instagram.com/refresh_access_token", timeout=30,
                     params={"grant_type": "ig_refresh_token", "access_token": token()})
    corpo = r.json()
    if "access_token" not in corpo:
        raise ErroInstagram(f"Falha ao renovar token: {corpo}")
    return corpo["access_token"], corpo.get("expires_in")
