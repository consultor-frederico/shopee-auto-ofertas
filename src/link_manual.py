"""Link manual: você manda o link de um produto da Shopee e o robô gera o SEU link de afiliado.

Fluxo: extrai o código do produto do link → consulta a API da Shopee (com os seus segredos) →
guarda a oferta na fila como pendente → manda o link de afiliado e o número "ok <id>" para o
seu Telegram PRIVADO. Nada é publicado aqui; a postagem depende do seu "ok".

Uso: LINK="https://shopee..." python -m src.link_manual
Segredos: SHOPEE_APP_ID, SHOPEE_APP_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_PRIVADO.
"""
import html
import os
import sys

from . import config, garimpar, shopee, telegram, video_manual, whatsapp_kit
from .garimpar import agora, carregar_fila, salvar_fila


def _responder(chat, texto):
    telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"})


def _mandar_oferta(chat, o):
    """Foto do produto (se houver) com o link e o comando 'ok <id>' tocável (toque para copiar)."""
    nome = html.escape(o["nome"])
    texto = (
        f"🛍️ <b>Link manual pronto</b>\n\n"
        f"{nome}\n"
        f"💰 R$ {o['preco_fmt']} · ⭐ {o['nota']} · {o['vendas']}+ vendidos\n"
        f"🏬 {html.escape(o['loja'])}\n\n"
        f"🔗 Seu link de afiliado:\n{html.escape(o['link_afiliado'])}"
    )
    teclado = '{"inline_keyboard":[[{"text":"✅ Aprovar","callback_data":"ok:%s"}]]}' % o["id"]
    if o.get("imagem"):
        try:
            telegram._api("sendPhoto", data={"chat_id": chat, "photo": o["imagem"], "caption": texto,
                                             "parse_mode": "HTML", "reply_markup": teclado})
            return
        except Exception as e:
            print(f"::warning::Foto não enviada ({e}); mandando só o texto.")
    telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "parse_mode": "HTML",
                                       "disable_web_page_preview": "true", "reply_markup": teclado})
    # texto pronto para copiar e colar no WhatsApp: preço que pode mudar + aviso de link de afiliado
    telegram._api("sendMessage", data={"chat_id": chat, "text": "📋 Texto pronto para o WhatsApp:",
                                       "disable_web_page_preview": "true"})
    telegram._api("sendMessage", data={"chat_id": chat, "text": whatsapp_kit.texto_whatsapp(o),
                                       "disable_web_page_preview": "true"})


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
    _mandar_oferta(chat, o)
    print(f"✅ Link manual salvo: {o['id']} — {o['nome']}")


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
