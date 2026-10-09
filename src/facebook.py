"""Página do Facebook (Graph API com login do Facebook) — posts, comentários e exclusão de posts antigos.

Segredos: FB_PAGE_ID e FB_PAGE_TOKEN (token de página, de longa duração).
O mesmo token também apaga mídias do Instagram vinculado à página (instagram_manage_contents).
"""
import os

import requests

VERSAO = "v23.0"
API = f"https://graph.facebook.com/{VERSAO}"


class ErroFacebook(RuntimeError):
    pass


def _env(n):
    return (os.getenv(n) or "").strip()


def configurado():
    return bool(_env("FB_PAGE_ID") and _env("FB_PAGE_TOKEN"))


def _req(metodo, caminho, params=None, json=None, data=None):
    params = dict(params or {})
    params["access_token"] = _env("FB_PAGE_TOKEN")
    r = requests.request(metodo, f"{API}/{caminho}", params=params, json=json, data=data, timeout=120)
    try:
        corpo = r.json()
    except ValueError:
        corpo = {"raw": r.text[:300]}
    if r.status_code >= 400 or (isinstance(corpo, dict) and "error" in corpo):
        e = corpo.get("error", corpo) if isinstance(corpo, dict) else corpo
        raise ErroFacebook(f"HTTP {r.status_code}: {e}")
    return corpo


def pagina():
    return _req("GET", _env("FB_PAGE_ID"), params={"fields": "id,name,instagram_business_account{id,username}"})


def postar_foto(url_imagem, legenda):
    """Devolve o id do post (page_postid)."""
    r = _req("POST", f"{_env('FB_PAGE_ID')}/photos", data={"url": url_imagem, "caption": legenda})
    return r.get("post_id") or r.get("id")


def postar_video(url_video, legenda):
    r = _req("POST", f"{_env('FB_PAGE_ID')}/videos", data={"file_url": url_video, "description": legenda})
    return r.get("id")


def permalink(post_id):
    try:
        return _req("GET", post_id, params={"fields": "permalink_url"}).get("permalink_url", "")
    except ErroFacebook:
        return ""


def comentarios(objeto_id):
    itens, params = [], {"fields": "id,message,created_time,from{id,name}", "limit": 100, "filter": "toplevel"}
    corpo = _req("GET", f"{objeto_id}/comments", params=params)
    itens += corpo.get("data", [])
    while (corpo.get("paging") or {}).get("next"):
        r = requests.get(corpo["paging"]["next"], timeout=60)
        corpo = r.json()
        itens += corpo.get("data", [])
    return itens


def resposta_privada_botao(comment_id, texto, url, titulo_botao):
    """Mensagem no Messenger para quem comentou (resposta privada), com botão."""
    return _req("POST", f"{_env('FB_PAGE_ID')}/messages", json={
        "recipient": {"comment_id": comment_id},
        "message": {"attachment": {"type": "template", "payload": {
            "template_type": "button", "text": texto[:640],
            "buttons": [{"type": "web_url", "url": url, "title": titulo_botao}]}}}})


def resposta_privada(comment_id, texto):
    return _req("POST", f"{_env('FB_PAGE_ID')}/messages",
                json={"recipient": {"comment_id": comment_id}, "message": {"text": texto}})


def responder_comentario(comment_id, texto):
    return _req("POST", f"{comment_id}/comments", data={"message": texto})


def apagar(objeto_id):
    """Apaga um post da página OU uma mídia do Instagram vinculado (mesmo endpoint)."""
    return _req("DELETE", objeto_id)


if __name__ == "__main__":   # teste: python -m src.facebook
    if not configurado():
        print("⏸️  FB_PAGE_ID / FB_PAGE_TOKEN ainda não cadastrados.")
    else:
        try:
            p = pagina()
            print(f"::notice::Página: {p.get('name')} ({p.get('id')}) — Instagram vinculado: "
                  f"{(p.get('instagram_business_account') or {}).get('username')}")
            ig = (p.get("instagram_business_account") or {}).get("id")
            if ig:
                m = _req("GET", f"{ig}/media", params={"fields": "id,timestamp", "limit": 3})
                print(f"::notice::Acesso às mídias do Instagram pelo Facebook: ok ({len(m.get('data', []))} posts lidos)")
            me = _req("GET", "me", params={"fields": "id,name"})
            print(f"::notice::Token pertence a: {me.get('name')} ({me.get('id')}) — "
                  f"{'token de PÁGINA ✔' if me.get('id') == _env('FB_PAGE_ID') else 'ATENÇÃO: não é token da página'}")
        except Exception as e:
            print(f"::error::{e}")
            raise SystemExit(1)
