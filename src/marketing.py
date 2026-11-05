"""📣 Estratégia de marketing (05/11/2026, ok do Fred), doc "Garimpo VIP: estratégia de marketing (nov-dez 2026)".

1) divulgar   — terça e sexta 10:00: texto pronto no Telegram PRIVADO do Fred, com botão que abre o WhatsApp
                com o texto (lista de transmissão, status, grupos). O texto muda com a fase: normal, aquecimento
                da Black (12-19/11), Black (20-30/11) e Natal (dezembro).
2) lista_black — todo dia 08:30 de 12/11 a 30/11: mensagem "Lista da Black do Zé" FIXADA no canal do Telegram,
                 com as melhores ofertas que passaram no canal nos últimos 3 dias. A mesma mensagem é editada
                 a cada dia (não notifica de novo). Em 01/12 o robô desafixa. Não grava nada no repositório:
                 acha a mensagem pelo "fixado" do canal.

Uso: python -m src.marketing divulgar|lista_black|teste
Segredos: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_PRIVADO (divulgar), TELEGRAM_CHAT_ID (lista_black),
SHOPEE_APP_ID/SECRET (link com subId "tg").
"""
import html
import json
import os
import sys
from datetime import date, timedelta
from urllib.parse import quote

from . import config, telegram

INSTAGRAM = "instagram.com/garimpovip4"
CANAL_TG = "t.me/garimpovipofertas"
PAGINA = "garimpovipbr.github.io"
TITULO_LISTA = "🖤 LISTA DA BLACK DO ZÉ"
LISTA_INICIO, LISTA_FIM = (11, 12), (11, 30)   # (mês, dia)
LISTA_MAX = 8
LISTA_DIAS = 3


def fase(hoje=None):
    hoje = hoje or date.today()
    if hoje.month == 12:
        return "natal"
    if hoje.month == 11 and 20 <= hoje.day <= 30:
        return "black"
    if hoje.month == 11 and 12 <= hoje.day <= 19:
        return "aquecimento"
    return "normal"


TEXTOS = {
    "normal": [
        "Conhece o Garimpo VIP? 🤠 O Zé garimpa achadinhos que valem a pena na Shopee, no Mercado Livre e em lojas "
        "oficiais: só entra o que tem nota alta e muita gente comprando.\n\n"
        "E o melhor: você comenta o que tá procurando e ele te manda as melhores opções no direct.\n\n"
        f"👉 {INSTAGRAM}",
        "Tá procurando alguma coisa e cansou de cair em produto ruim? 😅\n\n"
        f"Comenta no @garimpovip4 o que você quer que o Zé acha pra você e manda no direct. É de graça!\n\n👉 {INSTAGRAM}",
    ],
    "aquecimento": [
        "A Black Friday tá chegando e tem muito \"desconto\" que é só preço inflado 😅\n\n"
        "O Zé do Garimpo VIP tá garimpando só o que vale. Comenta lá o que você quer comprar na Black "
        "que ele acha pra você e te manda no direct.\n\n"
        f"👉 {INSTAGRAM}\n⚡ As ofertas relâmpago saem primeiro no Telegram: {CANAL_TG}",
    ],
    "black": [
        "É Black Friday! 🖤\n\nA lista do Zé com as melhores ofertas do dia tá fixada no Telegram do Garimpo VIP "
        f"(atualiza todo dia): {CANAL_TG}\n\n"
        f"Procurando algo específico? Comenta no @garimpovip4 que o Zé acha pra você.\n👉 {INSTAGRAM}",
    ],
    "natal": [
        "Sem ideia de presente de Natal ou de amigo secreto? 🎄\n\n"
        "Todo dia às 20h o Zé do Garimpo VIP solta um kit de presentes (tem kit até R$50 pro amigo secreto, "
        "pra ela, pra ele, pra criançada...).\n\n"
        f"Fala o que você procura que ele acha pra você 👉 {INSTAGRAM}",
    ],
}


def texto_do_dia(hoje=None):
    hoje = hoje or date.today()
    op = TEXTOS[fase(hoje)]
    return op[(hoje.toordinal() // 3) % len(op)]   # terça e sexta da mesma semana caem em textos diferentes


def achado_do_dia():
    """Primeiro achado da vitrine da bio (data/vitrine.json), com o número que abre direto na página."""
    try:
        v = json.loads((config.RAIZ / "data" / "vitrine.json").read_text(encoding="utf-8"))
        it = next(i for i in v.get("itens") or [] if i.get("titulo") and i.get("preco"))
    except Exception:
        return ""
    num = it.get("num")
    onde = f"{PAGINA}/#{num}" if num else PAGINA
    return (f"Olha o que o Zé achou hoje 👀\n\n{it['titulo']} por R$ {it['preco']} ({it.get('loja') or 'loja'})\n\n"
            f"👉 Abre direto aqui: {onde}\n(tem mais achados na mesma página)")


def _botao_zap(texto):
    return {"inline_keyboard": [[{"text": "📲 Mandar no WhatsApp",
                                  "url": "https://api.whatsapp.com/send?text=" + quote(texto)}]]}


def divulgar(hoje=None):
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or not chat:
        print("⏸️  Faltam TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_PRIVADO.")
        return
    hoje = hoje or date.today()
    dia = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][hoje.weekday()]
    telegram._api("sendMessage", data={"chat_id": chat, "text":
                  f"📣 Divulgação de {dia}: toca no botão de cada texto para mandar na lista de transmissão, "
                  "no status ou em 1-2 grupos. Leva 2 minutos e foi o que mais trouxe gente até agora 💪"})
    textos = [texto_do_dia(hoje)] + ([achado_do_dia()] if fase(hoje) == "normal" else [])
    for t in filter(None, textos):
        telegram._api("sendMessage", data={"chat_id": chat, "text": t,
                                           "reply_markup": json.dumps(_botao_zap(t))})
    print(f"📣 Divulgação ({fase(hoje)}) enviada: {len([t for t in textos if t])} texto(s).")


# ------------------------------------------------------------------ Lista da Black no Telegram

def _na_temporada(hoje):
    return LISTA_INICIO <= (hoje.month, hoje.day) <= LISTA_FIM


def ofertas_da_lista(fila, hoje=None):
    from .garimpar import FMT, agora
    limite = (agora() - timedelta(days=LISTA_DIAS)).strftime(FMT)
    ofs = [o for o in fila["ofertas"].values()
           if o.get("telegram") == "ok" and (o.get("telegram_em") or "") >= limite
           and o.get("status") in ("pendente", "postado") and o.get("link_afiliado") and o.get("preco_fmt")]
    ofs.sort(key=lambda o: (o.get("uau") or 0, o.get("vendas") or 0), reverse=True)
    escolhidas, familias = [], set()
    from .variedade import familia
    for o in ofs:
        f = familia(o)
        if f in familias:
            continue
        familias.add(f)
        escolhidas.append(o)
        if len(escolhidas) >= LISTA_MAX:
            break
    return escolhidas


def texto_lista(ofs, hoje=None):
    from . import vendas
    hoje = hoje or date.today()
    linhas = [f"<b>{TITULO_LISTA}</b>", f"<i>Atualizada em {hoje.strftime('%d/%m')} • muda todo dia até 30/11</i>", ""]
    for i, o in enumerate(ofs, 1):
        link = html.escape(vendas.do_canal(o, "tg"), quote=True)
        linhas.append(f"{i}. <a href=\"{link}\">{html.escape(o.get('titulo') or o.get('nome', ''))[:70]}</a> — "
                      f"<b>R$ {o['preco_fmt']}</b>")
    linhas += ["", "🔎 Procurando outra coisa? Comenta no Instagram @garimpovip4 o que você quer que o Zé acha pra você.",
               "<i>Preços conferidos quando a oferta saiu no canal: podem mudar na loja. "
               "Links de afiliado: você paga o mesmo e ajuda o Garimpo VIP 💛</i>"]
    return "\n".join(linhas)[:4000]


def _fixada(canal):
    try:
        pin = telegram._api("getChat", data={"chat_id": canal}).get("pinned_message") or {}
    except Exception as e:
        print(f"⚠️  Não li a mensagem fixada do canal ({e})")
        return None
    return pin if TITULO_LISTA in (pin.get("text") or "") else None


def lista_black(hoje=None):
    from .garimpar import carregar_fila
    hoje = hoje or date.today()
    canal = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or not canal:
        print("⏸️  Faltam TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID.")
        return
    pin = _fixada(canal)
    if not _na_temporada(hoje):
        if pin and hoje > date(hoje.year, *LISTA_FIM):
            telegram._api("unpinChatMessage", data={"chat_id": canal, "message_id": pin["message_id"]})
            print("📌 Black acabou: Lista da Black desafixada.")
        else:
            print("⏸️  Fora da temporada da Lista da Black (12 a 30/11).")
        return
    ofs = ofertas_da_lista(carregar_fila(), hoje)
    if len(ofs) < 3:
        print(f"⚠️  Só {len(ofs)} ofertas no canal nos últimos {LISTA_DIAS} dias: a lista fica como está.")
        return
    texto = texto_lista(ofs, hoje)
    dados = {"chat_id": canal, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if pin:
        try:
            telegram._api("editMessageText", data=dict(dados, message_id=pin["message_id"]))
            print(f"📝 Lista da Black atualizada ({len(ofs)} ofertas).")
            return
        except Exception as e:
            if "not modified" in str(e).lower():
                print("📝 Lista da Black já estava igual.")
                return
            print(f"⚠️  Não consegui editar a lista fixada ({e}); mando uma nova.")
    msg = telegram._api("sendMessage", data=dados)
    telegram._api("pinChatMessage", data={"chat_id": canal, "message_id": msg["message_id"],
                                          "disable_notification": "true"})
    print(f"📌 Lista da Black enviada e fixada ({len(ofs)} ofertas).")


def teste():
    """Mostra no log o que sairia (sem mandar nada), em cada fase."""
    for d in (date(2026, 11, 10), date(2026, 11, 14), date(2026, 11, 25), date(2026, 12, 5)):
        print(f"\n===== {d} ({fase(d)}) =====\n{texto_do_dia(d)}")
    print(f"\n===== achado do dia =====\n{achado_do_dia()}")
    from .garimpar import carregar_fila
    ofs = ofertas_da_lista(carregar_fila())
    print(f"\n===== Lista da Black (prévia, {len(ofs)} ofertas) =====")
    for o in ofs:
        print(f"- {o.get('titulo')} — R$ {o['preco_fmt']} (uau {o.get('uau')}, {o.get('vendas')} vendas)")


if __name__ == "__main__":
    acao = {"divulgar": divulgar, "lista_black": lista_black, "teste": teste}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if not acao:
        raise SystemExit("Uso: python -m src.marketing divulgar|lista_black|teste")
    acao()
