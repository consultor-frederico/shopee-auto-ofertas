"""Kit do Canal do WhatsApp: o WhatsApp não tem API para postar em canais, então o robô
prepara a oferta e manda no Telegram PRIVADO do Fred. Lá chegam a arte e o texto já no
formato do WhatsApp, com um botão "Mandar no WhatsApp" que abre o WhatsApp com o texto pronto.

Uso: python -m src.whatsapp_kit
Segredos: TELEGRAM_BOT_TOKEN (o mesmo bot do canal) e TELEGRAM_CHAT_PRIVADO (o seu chat com o bot).
Se TELEGRAM_CHAT_PRIVADO ainda não existir, a rodada mostra no log o número do seu chat
(mande qualquer mensagem para o bot antes).
"""
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from . import config, imagem, precos, telegram
from .garimpar import BRT, FMT, agora, carregar_fila, salvar_fila
from .imagem import plataforma
from .precos import tem_variacoes

POR_EXECUCAO = int(os.getenv("WHATSAPP_POR_EXECUCAO", "1"))
LINK_TELEGRAM = "https://t.me/garimpovipofertas"


def chat_privado():
    return os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()


def descobrir_chat():
    """Mostra no log os chats privados que falaram com o bot (para cadastrar o segredo)."""
    try:
        ups = telegram._api("getUpdates", data={"limit": 100})
    except Exception as e:
        print(f"::warning::Não consegui ler as mensagens do bot: {e}")
        return
    vistos = {}
    for u in ups:
        chat = (u.get("message") or {}).get("chat") or {}
        if chat.get("type") == "private":
            vistos[chat["id"]] = chat.get("first_name") or chat.get("username") or ""
    if not vistos:
        print("::warning::Mande um 'oi' para o bot no Telegram e rode de novo para descobrir o número do seu chat.")
    for cid, nome in vistos.items():
        print(f"::notice::Chat privado encontrado: {nome} → cadastre o segredo TELEGRAM_CHAT_PRIVADO = {cid}")


def candidatas(fila):
    limite = agora() - timedelta(days=config.DIAS_VALIDADE_PENDENTE)
    ofs = [o for o in fila["ofertas"].values()
           if o.get("status") in ("pendente", "postado") and not o.get("whatsapp")
           and o.get("link_afiliado") and o.get("titulo") and o.get("imagem") and not o.get("video_manual")
           and datetime.strptime(o["criado_em"], FMT).replace(tzinfo=BRT) >= limite]
    ofs.sort(key=lambda o: o.get("pontos", 0), reverse=True)
    escolhidas, cats = [], set()
    for o in ofs:   # alterna nichos
        if len(escolhidas) < POR_EXECUCAO and o.get("categoria") not in cats:
            escolhidas.append(o)
            cats.add(o.get("categoria"))
    for o in ofs:
        if len(escolhidas) < POR_EXECUCAO and o not in escolhidas:
            escolhidas.append(o)
    return escolhidas


def texto_whatsapp(o):
    """Texto no formato do WhatsApp (*negrito*, ~riscado~, _itálico_)."""
    gancho = []
    for linha in (o.get("legenda") or "").splitlines():
        t = linha.strip()
        if not t or t.startswith(("#", "📲", "🔖", "🕒")) or "QUERO" in t.upper() or "R$" in t:
            continue
        gancho.append(t.replace("*", ""))
    gancho = gancho[:2]
    apartir = "a partir de " if tem_variacoes(o) else ""
    preco = f"💰 {apartir}*R$ {o['preco_fmt']}*"
    if o.get("preco_de"):
        preco = f"💰 de ~R$ {telegram._brl(o['preco_de'])}~ por {apartir}*R$ {o['preco_fmt']}*"
        if o.get("desconto"):
            preco += f" (-{o['desconto']}%)"
    nota = (f"{o['avaliacao_pct']:.0f}% aprovação" if o.get("avaliacao_pct")
            else f"nota {o.get('nota', 0):.1f}".replace(".", ","))
    vendas = f"{o.get('vendas', 0):,}".replace(",", ".")
    loja = telegram.NOME_LOJA.get(plataforma(o), plataforma(o).title())
    partes = []
    if o.get("nivel") == "achado":
        partes += ["💎 *ACHADO ESCONDIDO*", ""]
    partes += [f"🔥 *{o['titulo'].replace('*', '')}*", ""]
    if gancho:
        partes += gancho + [""]
    partes += [preco, f"⭐ {nota} • {vendas}+ vendidos", "",
               f"🛒 Compre na {loja}:", o["link_afiliado"], "",
               f"_{precos.aviso(o)}_",
               "_Link de afiliado: você paga o mesmo e ajuda o Garimpo VIP 💛_"]
    return "\n".join(partes)


def enviar(o, arte):
    chat = chat_privado()
    texto = texto_whatsapp(o)
    with open(arte, "rb") as f:
        telegram._api("sendPhoto", data={"chat_id": chat, "caption": "📲 Arte para o Canal do WhatsApp (salve e poste com o texto abaixo)"},
                      files={"photo": f})
    botao = '{"inline_keyboard":[[{"text":"📲 Mandar no WhatsApp","url":"%s"}]]}' % (
        "https://wa.me/?text=" + quote(texto))
    try:
        telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "reply_markup": botao,
                                           "disable_web_page_preview": "true"})
    except Exception as e:   # texto longo demais para o botão: manda só o texto para copiar
        print(f"⚠️  Sem botão do WhatsApp ({e}); enviando só o texto.")
        telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"})


def rodar():
    if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        print("⏸️  Bot do Telegram não configurado — kit do WhatsApp em espera.")
        return
    if not chat_privado():
        print("⏸️  Falta o segredo TELEGRAM_CHAT_PRIVADO.")
        descobrir_chat()
        return
    fila = carregar_fila()
    ofs = candidatas(fila)
    if not ofs:
        print("Nenhuma oferta nova para o WhatsApp.")
        return
    pasta = Path(tempfile.mkdtemp())
    enviadas = 0
    for o in ofs:
        if precos.conferir(o) in ("sumiu", "subiu"):
            o["whatsapp"] = "descartado"
            continue
        try:
            arte = pasta / f"{o['id']}.jpg"
            imagem.gerar(o, arte, foto=imagem._baixar_foto(o["imagem"]))
            enviar(o, arte)
            o["whatsapp"] = "ok"
            o["whatsapp_em"] = agora().strftime(FMT)
            enviadas += 1
            print(f"📲 {o.get('categoria', ''):<11} R$ {o['preco_fmt']:>8}  {o['titulo']}")
        except Exception as e:
            o["whatsapp_tentativas"] = o.get("whatsapp_tentativas", 0) + 1
            if o["whatsapp_tentativas"] >= 2:
                o["whatsapp"] = "erro"
            print(f"::warning::Kit do WhatsApp falhou para {o['id']}: {e}")
        time.sleep(2)
    salvar_fila(fila)
    print(f"🏁 {enviadas} ofertas enviadas para você repassar no WhatsApp.")


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
