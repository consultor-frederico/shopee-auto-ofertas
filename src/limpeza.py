"""Apaga do Instagram, da página do Facebook e do YouTube os posts de oferta com mais de N dias.

Preço de oferta muda — post velho com preço antigo confunde quem vê. Só mexe nas ofertas que o
próprio robô postou (fila); posts manuais, chamadas do Telegram e vídeos do Zé ficam.
Uso: python -m src.limpeza   (DRY_RUN=1 só mostra o que apagaria)
"""
import os
import sys
from datetime import datetime, timedelta

from . import config, facebook, youtube
from .garimpar import BRT, FMT, agora, carregar_fila, salvar_fila


def rodar():
    if not facebook.configurado():
        print("⏸️  FB_PAGE_ID / FB_PAGE_TOKEN ausentes — a exclusão usa a conexão do Facebook.")
        return
    teste = os.getenv("DRY_RUN") == "1"
    limite = agora() - timedelta(days=config.DIAS_APAGAR_POSTS)
    fila = carregar_fila()
    apagados = falhas = 0
    for o in fila["ofertas"].values():
        if o.get("status") != "postado" or not o.get("postado_em"):
            continue
        if datetime.strptime(o["postado_em"], FMT).replace(tzinfo=BRT) >= limite:
            continue
        print(f"🗑️  {o['postado_em'][:10]} — {o.get('titulo')}")
        if teste:
            continue
        ok = True
        for campo, rede, apagar in (("id_post", "Instagram", facebook.apagar),
                                    ("fb_post", "Facebook", facebook.apagar),
                                    ("yt_video", "YouTube", youtube.apagar)):
            if not o.get(campo) or o.get(f"{campo}_apagado"):
                continue
            if campo == "yt_video" and not youtube.configurado():
                continue
            try:
                apagar(o[campo])
                o[f"{campo}_apagado"] = agora().strftime(FMT)
            except Exception as e:
                ok = False
                o["erro_apagar"] = f"{rede}: {str(e)[:200]}"
                print(f"::warning::Não apaguei no {rede}: {e}")
        if ok:
            o["status"] = "apagado"
            apagados += 1
        else:
            falhas += 1
    salvar_fila(fila)
    print(f"🏁 {apagados} posts antigos apagados, {falhas} com falha (tenta de novo amanhã).")


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
