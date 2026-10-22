"""Link manual: você manda o link de um produto da Shopee e o robô gera o SEU link de afiliado.

Fluxo: extrai o código do produto do link → consulta a API da Shopee (com os seus segredos) →
guarda a oferta na fila como pendente → manda o link de afiliado e o número "ok <id>" para o
seu Telegram PRIVADO. Nada é publicado aqui; a postagem depende do seu "ok".

Uso: LINK="https://shopee..." python -m src.link_manual
Segredos: SHOPEE_APP_ID, SHOPEE_APP_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_PRIVADO.
"""
import os
import sys

from . import config, garimpar, shopee, telegram, video_manual
from .garimpar import agora, carregar_fila, salvar_fila


def _responder(chat, texto):
    telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"})


def rodar():
    link = (os.getenv("LINK") or "").strip()
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if not link:
        print("::error::Informe o link do produto (input 'link').")
        sys.exit(1)
    if not chat or not os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        print("::error::Faltam TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_PRIVADO.")
        sys.exit(1)
    item_id = video_manual.extrair_item_id(link)
    if not item_id:
        _responder(chat, f"❓ Não consegui ler o produto deste link: {link}")
        return
    nos = shopee.buscar_por_item(item_id)
    if not nos or not nos[0].get("offerLink"):
        _responder(chat, f"❓ A API da Shopee não devolveu oferta para o produto {item_id}. Ele pode estar fora do ar ou sem programa de afiliado.")
        return
    o = garimpar.normalizar(nos[0], "manual", "link manual")
    o["status"] = "pendente"
    o["origem"] = "link_manual"
    o["criado_em"] = agora().strftime(garimpar.FMT)
    fila = carregar_fila()
    fila["ofertas"][o["id"]] = o
    salvar_fila(fila)
    preco = f"R$ {o['preco_fmt']}"
    _responder(chat, (
        f"🛍️ Link manual pronto\n\n"
        f"{o['nome']}\n"
        f"💰 {preco} · ⭐ {o['nota']} · {o['vendas']}+ vendidos\n"
        f"🏬 {o['loja']}\n\n"
        f"🔗 Seu link de afiliado:\n{o['link_afiliado']}\n\n"
        f"Para aprovar, responda: ok {o['id']}"
    ))
    print(f"✅ Link manual salvo: {o['id']} — {o['nome']}")


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
