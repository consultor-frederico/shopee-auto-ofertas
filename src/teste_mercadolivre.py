"""Teste de leitura da busca pública do Mercado Livre. Só lê e manda o resultado para o seu Telegram privado.

Uso: python -m src.teste_mercadolivre "lego"
"""
import os
import sys

import requests

from . import telegram

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GarimpoVIP/1.0)", "Accept": "application/json"}


def rodar(termo):
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    url = "https://api.mercadolibre.com/sites/MLB/search"
    try:
        r = requests.get(url, params={"q": termo, "limit": 5}, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        msg = f"❌ Mercado Livre: não consegui acessar a busca ({e})."
    else:
        if r.status_code != 200:
            msg = f"❌ Mercado Livre respondeu {r.status_code}: {r.text[:300]}"
        else:
            itens = (r.json() or {}).get("results", [])
            linhas = [f"✅ Mercado Livre respondeu. Busca: {termo} · {len(itens)} resultados"]
            for it in itens[:5]:
                linhas.append(f"• {it.get('title', '')[:80]} · R$ {it.get('price')} · vendidos: {it.get('sold_quantity', 'n/d')} · {it.get('permalink', '')}")
            linhas.append(f"Campos disponíveis: {', '.join(sorted(itens[0].keys())[:30]) if itens else 'nenhum'}")
            msg = "\n".join(linhas)
    if chat and os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        telegram._api("sendMessage", data={"chat_id": chat, "text": msg, "disable_web_page_preview": "true"})
    print(msg)


if __name__ == "__main__":
    rodar(sys.argv[1] if len(sys.argv) > 1 else "lego")
