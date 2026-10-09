"""Publica na página do Facebook as últimas ofertas do Instagram que ainda não estão lá.

Usa a mídia do próprio post do Instagram (media_url). Uso: QUANTOS=1 python -m src.facebook_recentes
"""
import os
import sys

from . import facebook, instagram
from .garimpar import carregar_fila, salvar_fila
from .postar import legenda_facebook


def rodar():
    quantos = int(os.getenv("QUANTOS") or "1")
    fila = carregar_fila()
    postados = sorted([o for o in fila["ofertas"].values() if o.get("status") == "postado"
                       and o.get("id_post") and not o.get("fb_post")],
                      key=lambda o: o.get("postado_em", ""), reverse=True)[:quantos]
    if not postados:
        print("Nada novo para publicar no Facebook.")
        return
    for o in postados:
        m = instagram._req("GET", o["id_post"], params={"fields": "media_type,media_url"})
        url = m.get("media_url")
        leg = legenda_facebook(o.get("legenda", o.get("titulo", "")))
        if m.get("media_type") == "VIDEO":
            pid = facebook.postar_video(url, leg)
        else:
            pid = facebook.postar_foto(url, leg)
        o["fb_post"] = pid
        salvar_fila(fila)
        print(f"::notice::📘 Publicado no Facebook: {o.get('titulo')} ({pid}) — {facebook.permalink(pid)}")


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
