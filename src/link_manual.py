"""Link manual: você manda o link de um produto da Shopee e o robô gera o SEU link de afiliado.

Fluxo: extrai o código do produto do link → consulta a API da Shopee (com os seus segredos) →
guarda a oferta na fila como pendente → manda o link de afiliado e o número "ok <id>" para o
seu Telegram PRIVADO. Nada é publicado aqui; a postagem depende do seu "ok".
Link que não é de produto (página de campanha, sorteio, cupom): só gera o link de afiliado
marcado por canal (Telegram e story) e manda no Telegram privado, sem entrar na fila.

Uso: LINK="https://shopee..." python -m src.link_manual
Segredos: SHOPEE_APP_ID, SHOPEE_APP_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_PRIVADO.
"""
import os
import sys
import tempfile

from . import config, garimpar, imagem, shopee, telegram, vendas, video_manual, whatsapp_kit
from .garimpar import agora, carregar_fila, salvar_fila


def _responder(chat, texto):
    telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"})


def _mandar_oferta(chat, o):
    """Arte completa do produto com o texto padrão (copiável) e o botão de aprovação, numa mensagem."""
    texto = whatsapp_kit.texto_whatsapp(o)[:1000]   # legenda do Telegram aceita até 1024 caracteres
    teclado = '{"inline_keyboard":[[{"text":"✅ Aprovar","callback_data":"ok:%s"}]]}' % o["id"]
    try:
        pasta = tempfile.mkdtemp()
        arte = os.path.join(pasta, f"{o['id']}.jpg")
        imagem.gerar(o, arte, foto=imagem._baixar_foto(o["imagem"]))
        with open(arte, "rb") as f:
            telegram._api("sendPhoto", data={"chat_id": chat, "caption": texto, "reply_markup": teclado},
                          files={"photo": f})
        return
    except Exception as e:
        print(f"::warning::Arte não gerada ({e}); mandando o texto sem arte.")
    telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true",
                                       "reply_markup": teclado})


def _link_de_pagina(chat, link):
    """Página da Shopee que não é produto: um link de afiliado por canal, sem entrar na fila."""
    canais = {"Telegram": ["garimpo", "telegram", "campanha"], "Story": ["garimpo", "story", "campanha"]}
    linhas = []
    for nome, subs in canais.items():
        try:
            curto = vendas.link_curto(link, subs)
        except Exception as e:
            print(f"::warning::{nome}: {e}")
            curto = ""
        linhas.append(f"{nome}: {curto or 'não gerou'}")
    if not any(l.startswith(("Telegram: http", "Story: http")) for l in linhas):
        _responder(chat, f"❓ A API da Shopee não gerou link de afiliado para esta página: {link}")
        print("::error::Nenhum link gerado.")
        sys.exit(1)
    _responder(chat, "🔗 Link de afiliado da página\n" + link + "\n\n" + "\n".join(linhas))
    print("✅ " + " | ".join(linhas))


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
        _link_de_pagina(chat, link)
        return
    nos = shopee.buscar_por_item(item_id)
    if not nos or not nos[0].get("offerLink"):
        _responder(chat, f"❓ A API da Shopee não devolveu oferta para o produto {item_id}. Ele pode estar fora do ar ou sem programa de afiliado.")
        return
    o = garimpar.normalizar(nos[0], "manual", "link manual")
    o["titulo"] = o["nome"]   # arte e texto usam "titulo"
    o["legenda"] = ""
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
