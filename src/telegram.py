"""Envio das ofertas para o canal do Telegram (API oficial de bots).

Segredos: TELEGRAM_BOT_TOKEN (do @BotFather) e TELEGRAM_CHAT_ID (ex.: @garimpovip ou -100...).
Teste: python -m src.telegram teste
"""
import html
import os
import sys

import requests

from .imagem import plataforma

NOME_LOJA = {"shopee": "Shopee", "aliexpress": "AliExpress"}


def configurado():
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_CHAT_ID", "").strip())


def _api(metodo, data=None, files=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", data=data, files=files, timeout=120)
    corpo = r.json()
    if not corpo.get("ok"):
        raise RuntimeError(f"Telegram: {corpo.get('description', corpo)}")
    return corpo["result"]


def _brl(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def legenda(oferta):
    """Texto do canal: gancho da IA (sem o 'comente EU QUERO' e sem hashtags) + bloco de preço."""
    linhas = []
    for linha in (oferta.get("legenda") or "").splitlines():
        t = linha.strip()
        if not t or t.startswith("#") or "EU QUERO" in t.upper() or "R$" in t:
            continue
        linhas.append(html.escape(t))
    linhas = linhas[:3]
    preco = f"💰 <b>R$ {oferta['preco_fmt']}</b>"
    if oferta.get("preco_de"):
        preco = f"💰 de <s>R$ {_brl(oferta['preco_de'])}</s> por <b>R$ {oferta['preco_fmt']}</b>"
        if oferta.get("desconto"):
            preco += f"  (-{oferta['desconto']}%)"
    nota = (f"{oferta['avaliacao_pct']:.0f}% aprovação" if oferta.get("avaliacao_pct")
            else f"{oferta.get('nota', 0):.1f}".replace(".", ","))
    vendas = f"{oferta.get('vendas', 0):,}".replace(",", ".")
    loja = NOME_LOJA.get(plataforma(oferta), plataforma(oferta).title())
    partes = [f"🔥 <b>{html.escape(oferta['titulo'])}</b>", ""]
    partes += linhas + [""] if linhas else []
    partes += [preco, f"⭐ {nota}  •  {vendas}+ vendidos", f"🏷️ Oferta {loja}", "",
               "<i>Link de afiliado: você paga o mesmo e ajuda o Garimpo VIP 💛</i>"]
    return "\n".join(partes)[:1024]


def enviar_oferta(oferta, arquivo, formato):
    """Envia a arte (foto) ou o Reels (vídeo) com botão para a oferta."""
    loja = NOME_LOJA.get(plataforma(oferta), "loja")
    teclado = '{"inline_keyboard":[[{"text":"🛒 Ver oferta na %s","url":"%s"}]]}' % (
        loja, oferta["link_afiliado"].replace('"', ""))
    dados = {"chat_id": os.getenv("TELEGRAM_CHAT_ID").strip(), "caption": legenda(oferta),
             "parse_mode": "HTML", "reply_markup": teclado}
    with open(arquivo, "rb") as f:
        if formato == "reels":
            dados["supports_streaming"] = "true"
            return _api("sendVideo", data=dados, files={"video": f})
        return _api("sendPhoto", data=dados, files={"photo": f})


def teste():
    eu = _api("getMe")
    msg = _api("sendMessage", data={
        "chat_id": os.getenv("TELEGRAM_CHAT_ID").strip(), "parse_mode": "HTML",
        "text": "✨ <b>Canal Garimpo VIP no ar!</b>\n\nAqui você recebe os melhores achadinhos "
                "garimpados todo dia, com link direto. 💎"})
    print(f"✅ Bot @{eu['username']} publicou no canal (mensagem {msg['message_id']}).")


if __name__ == "__main__":
    if not configurado():
        print("::error::Cadastre os segredos TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        sys.exit(1)
    try:
        teste()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
