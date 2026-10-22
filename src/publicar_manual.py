"""Publica um post de marca aprovado pelo Fred (artes em manuais/, textos em manuais/posts.json).

Uso: python -m src.publicar_manual <nome>      (ex.: ze1, ana2)
Trava: o post só sai na conta do perfil indicado no posts.json, e o token tem que ser dessa conta.
Trava anti-duplicata: cada post sai uma vez só (registro em data/manuais_publicados.json).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, instagram, postar, telegram

RAIZ = Path(__file__).resolve().parent.parent
POSTS = RAIZ / "manuais" / "posts.json"
REGISTRO = RAIZ / "data" / "manuais_publicados.json"
BRT = timezone(timedelta(hours=-3))


def _ler(caminho, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def enviar_whatsapp(nome, p):
    """Manda a arte e a legenda no seu Telegram privado, para você postar no grupo do WhatsApp."""
    if p["perfil"] != "garimpo":
        raise SystemExit("Só o Garimpo VIP vai para o WhatsApp. Post da Ana não sai daqui.")
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PAGES_URL ausente: o deploy do GitHub Pages não rodou.")
    url = f"{base}/manuais/{nome}.png"
    postar._esperar_url(url)
    telegram._api("sendPhoto", data={"chat_id": os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip(), "photo": url, "caption": p["legenda"]})
    print(f"📲 {nome} enviado no seu Telegram privado para postar no WhatsApp")


def rodar(nome, destino="instagram"):
    posts = {p["nome"]: p for p in _ler(POSTS, [])}
    p = posts.get(nome)
    if not p:
        raise SystemExit(f"Post {nome} não existe em manuais/posts.json")
    if destino == "whatsapp":
        return enviar_whatsapp(nome, p)
    if p["perfil"] != config.PERFIL:
        raise SystemExit(f"Post {nome} é do perfil {p['perfil']}, mas a rodada é {config.PERFIL}. Nada foi publicado.")
    registro = _ler(REGISTRO, {})
    if nome in registro:
        print(f"⏭️  {nome} já foi publicado em {registro[nome]['em']}. Nada a fazer.")
        return
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PAGES_URL ausente: o deploy do GitHub Pages não rodou.")
    url = f"{base}/manuais/{nome}.png"
    postar._esperar_url(url)
    ig_id = instagram.conferir_conta()["user_id"]
    cont = instagram.criar_container(ig_id, p["legenda"], imagem_url=url)
    instagram.aguardar_container(cont)
    media_id = instagram.publicar(ig_id, cont)
    registro[nome] = {"media_id": media_id, "perfil": p["perfil"],
                      "em": datetime.now(BRT).strftime("%d/%m/%Y %H:%M")}
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {nome} publicado em @{config.ARROBA.lstrip('@')} (media {media_id})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python -m src.publicar_manual <nome> [instagram|whatsapp]")
    rodar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "instagram")
