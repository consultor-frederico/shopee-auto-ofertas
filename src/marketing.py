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
    baratas = ofertas_baratas(carregar_fila())
    print(f"\n===== Lista até R$50 (prévia sem conferir preço, {len(baratas)} candidatas) =====")
    for o in baratas:
        print(f"- {o.get('titulo')} — R$ {o['preco_fmt']} (uau {o.get('uau')}, {o.get('vendas')} vendas)")


# ------------------------------------------------------------------ Lista "achados até R$50" (revisão 08/11/2026)
# Ok do Fred em 08/11/2026 ("tudo que o robô tiver que fazer está autorizado"), doc "Garimpo VIP: revisão da
# estratégia e plano da Black Friday". O que vendeu até agora foi barato e veio de quem confia no Fred, então a
# oferta-chave da Black é uma lista de achados até R$50 por dia, no canal do Telegram e pronta para o Canal do
# WhatsApp (o Fred repassa). Dias: 11/11 (11.11 da Shopee) e 20 a 30/11; em 27/11 (Black Friday) sai 3 vezes.
# Junto vai a arte do 1º achado para o Status do WhatsApp do Fred.
BARATA_TETO = 50.0
BARATA_MAX = 6
BARATA_DIAS = ((11, 11),) + tuple((11, d) for d in range(20, 31))


def _turno():
    from .garimpar import agora
    h = agora().hour
    return 0 if h < 10 else (1 if h < 16 else 2)


def ofertas_baratas(fila, turno=0):
    """Até BARATA_MAX achados até R$50 que passaram no canal nos últimos 3 dias (ou estão na fila
    aprovados), um por família, os melhores primeiro. `turno` pula os já usados nas listas anteriores do dia."""
    from .garimpar import FMT, agora
    from .variedade import familia
    limite = (agora() - timedelta(days=LISTA_DIAS)).strftime(FMT)
    ofs = [o for o in fila["ofertas"].values()
           if o.get("status") in ("pendente", "postado") and o.get("link_afiliado") and o.get("preco_fmt")
           and 0 < (o.get("preco") or 0) <= BARATA_TETO and (o.get("uau") or 0) >= 7
           and max(o.get("telegram_em") or "", o.get("criado_em") or "") >= limite]
    ofs.sort(key=lambda o: (o.get("uau") or 0, o.get("vendas") or 0), reverse=True)
    unicas, familias = [], set()
    for o in ofs:
        f = familia(o)
        if f in familias:
            continue
        familias.add(f)
        unicas.append(o)
    ini = turno * BARATA_MAX
    return unicas[ini:ini + BARATA_MAX * 2] or unicas[:BARATA_MAX * 2]


def _conferidas(ofs):
    from . import precos
    boas = []
    for o in ofs:
        try:
            if precos.conferir(o) in ("sumiu", "subiu") or (o.get("preco") or 0) > BARATA_TETO:
                continue
        except Exception as e:
            print(f"⚠️  Não conferi {o.get('id')}: {e}")
            continue
        boas.append(o)
        if len(boas) >= BARATA_MAX:
            break
    return boas


def _titulo_barata(hoje):
    if (hoje.month, hoje.day) == (11, 11):
        return "🛒 11.11 DO ZÉ: ACHADOS ATÉ R$50"
    if (hoje.month, hoje.day) == (11, 27):
        return "🖤 BLACK FRIDAY DO ZÉ: ACHADOS ATÉ R$50"
    return "🖤 BLACK DO ZÉ: ACHADOS ATÉ R$50"


def texto_barata(ofs, canal, hoje=None, html_ok=True):
    from . import vendas
    hoje = hoje or date.today()
    tit = _titulo_barata(hoje)
    if html_ok:
        linhas = [f"<b>{tit}</b>", ""]
        for i, o in enumerate(ofs, 1):
            link = html.escape(vendas.do_canal(o, canal), quote=True)
            linhas.append(f"{i}. <a href=\"{link}\">{html.escape(o.get('titulo') or o.get('nome', ''))[:70]}</a> — "
                          f"<b>R$ {o['preco_fmt']}</b>")
        linhas += ["", f"<i>Preços conferidos em {hoje.strftime('%d/%m')} e podem mudar a qualquer momento. "
                   "Links de afiliado: você paga o mesmo e ajuda o Garimpo VIP 💛</i>"]
    else:
        linhas = [f"*{tit}*", ""]
        for i, o in enumerate(ofs, 1):
            linhas += [f"{i}. *{(o.get('titulo') or o.get('nome', ''))[:70]}*", f"💰 R$ {o['preco_fmt']}",
                       vendas.do_canal(o, canal), ""]
        linhas += [f"_Preços conferidos em {hoje.strftime('%d/%m')} e podem mudar a qualquer momento. "
                   "Links de afiliado: você paga o mesmo e ajuda o Garimpo VIP 💛_"]
    return "\n".join(linhas)[:4000]


def lista_barata(hoje=None, forcar=False):
    from .garimpar import carregar_fila
    hoje = hoje or date.today()
    if not forcar and (hoje.month, hoje.day) not in BARATA_DIAS:
        print("⏸️  Hoje não tem lista até R$50 (11/11 e 20 a 30/11).")
        return
    canal = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    privado = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or not (canal or privado):
        print("⏸️  Faltam TELEGRAM_BOT_TOKEN ou os chats do Telegram.")
        return
    ofs = _conferidas(ofertas_baratas(carregar_fila(), _turno()))
    if len(ofs) < 3:
        print(f"⚠️  Só {len(ofs)} achados até R$50 conferidos: lista não sai hoje.")
        return
    if canal:
        telegram._api("sendMessage", data={"chat_id": canal, "text": texto_barata(ofs, "tg", hoje),
                                           "parse_mode": "HTML", "disable_web_page_preview": "true"})
        print(f"📣 Lista até R$50 no canal do Telegram ({len(ofs)} achados).")
    if privado:
        _status_do_dia(privado, ofs[0])
        zap = texto_barata(ofs, "zap", hoje, html_ok=False)
        telegram._api("sendMessage", data={"chat_id": privado, "text":
                      "📲 Lista até R$50 para o Canal do WhatsApp: segura a mensagem abaixo → Copiar, e cola no Canal."})
        dados = {"chat_id": privado, "text": zap, "disable_web_page_preview": "true"}
        if len(quote(zap)) < 1800:
            dados["reply_markup"] = json.dumps(_botao_zap(zap))
        telegram._api("sendMessage", data=dados)
        print("📲 Lista até R$50 + arte do Status no Telegram privado.")


def _status_do_dia(chat, o):
    """Arte do achado (mesma do kit do WhatsApp) para o Status do Fred."""
    import tempfile
    from pathlib import Path
    from . import imagem, vendas
    try:
        arte = Path(tempfile.mkdtemp()) / f"status_{o['id']}.jpg"
        imagem.gerar(o, arte, foto=imagem._baixar_foto(o["imagem"]))
        legenda = (f"📲 Para o seu Status do WhatsApp: segura a foto → Salvar e posta com o texto abaixo.\n\n"
                   f"Achado do dia até R$50 👇 {o.get('titulo') or ''} por R$ {o['preco_fmt']}\n"
                   f"{vendas.do_canal(o, 'zap')}\nMais no canal: https://whatsapp.com/channel/0029Vb9As8d2ER6ZGIsRPo0z")
        with open(arte, "rb") as f:
            telegram._api("sendPhoto", data={"chat_id": chat, "caption": legenda[:1000]}, files={"photo": f})
    except Exception as e:
        print(f"⚠️  Arte do Status não saiu ({e})")


# ------------------------------------------------------------------ Relatório semanal (segunda 9h)

def relatorio(agora_=None):
    """Placar das metas da revisão de 08/11/2026 no Telegram privado do Fred, toda segunda 9h."""
    from datetime import datetime
    from . import cofre, vendas
    from .garimpar import BRT
    privado = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    agora_ = agora_ or datetime.now(BRT)
    hist = cofre.ler_json(config.RAIZ / "data" / "seguidores.json", [])
    atual = hist[-1]["contas"] if hist else {}
    semana = (agora_ - timedelta(days=7)).strftime("%Y-%m-%d")
    antes = next((h["contas"] for h in reversed(hist) if h["data"] <= semana), hist[0]["contas"] if hist else {})

    def linha(nome, chave, meta=None):
        a, b = atual.get(chave), antes.get(chave)
        if a is None:
            return f"• {nome}: sem medição"
        dif = f" ({a - b:+d} na semana)" if isinstance(b, int) else ""
        return f"• {nome}: {a}{dif}" + (f" | meta {meta}" if meta else "")

    busca = cofre.ler_json(config.RAIZ / "data" / "busca_ze.json", {})
    from .top import DONOS
    pessoas = {v.get("usuario") for k in ("comentarios", "dms") for v in (busca.get(k) or {}).values()
               if (v.get("em") or "") >= semana and (v.get("usuario") or "").lower() not in DONOS}
    try:
        _, sete = vendas.resumo(7, agora_)
        _, mes = vendas.resumo(agora_.day, agora_)
        vend = (f"• Vendas Shopee 7 dias: {sete['pedidos']} pedido(s), {vendas._brl(sete['comissao'])}\n"
                f"• Vendas Shopee no mês: {mes['pedidos']} | meta 10 em novembro (somar Mercado Livre e Awin à mão)")
    except Exception as e:
        vend = f"• Vendas: não consegui ler o relatório da Shopee ({str(e)[:80]})"
    texto = "\n".join([
        f"📊 Relatório de marketing — {agora_.strftime('%d/%m')}", "",
        linha("Instagram Garimpo", "ig_garimpo", "180 em 30/11"),
        linha("Telegram", "telegram"),
        "• Canal do WhatsApp: confira no app quantos seguem (o robô não enxerga)",
        "  Meta: Canal + Telegram = 100 até 20/11",
        linha("Facebook", "facebook"),
        f"• Busca do Zé: {len(pessoas)} pessoa(s) de fora na semana | meta 5",
        vend, "",
        "Medição de alcance e compartilhamentos: rotina 25 (Métricas).",
    ])
    if not privado or not os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        print(texto)
        return
    telegram._api("sendMessage", data={"chat_id": privado, "text": texto})
    print("📊 Relatório de marketing enviado.")


TEXTO_BUSCA = ("Tá procurando presente de Natal ou alguma coisa pra casa? 🎄\n\n"
               "Comenta no @garimpovip4 o que você quer que o Zé garimpa pra você e manda no direct 🤠 "
               "Só vendedor com nota alta e muita venda, e é de graça.\n\n"
               f"👉 {INSTAGRAM}")


def busca():
    """Kit avulso da Busca do Zé (08/11/2026): arte de Story + texto com botão para o WhatsApp."""
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or not chat:
        print("⏸️  Faltam TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_PRIVADO.")
        return
    arte = config.RAIZ / "assets" / "divulgacao" / "story_busca_ze.jpg"
    with open(arte, "rb") as f:
        telegram._api("sendPhoto", data={"chat_id": chat, "caption":
                      "📣 Arte para o seu Status do Instagram/WhatsApp: segura a foto → Salvar, e posta no Story. "
                      "Dá pra marcar o @garimpovip4 por cima."}, files={"photo": f})
    telegram._api("sendMessage", data={"chat_id": chat, "text": TEXTO_BUSCA,
                                       "reply_markup": json.dumps(_botao_zap(TEXTO_BUSCA))})
    print("📣 Kit da Busca do Zé enviado.")


if __name__ == "__main__":
    acao = {"divulgar": divulgar, "lista_black": lista_black, "teste": teste, "busca": busca,
            "lista_barata": lista_barata, "lista_barata_agora": lambda: lista_barata(forcar=True),
            "relatorio": relatorio}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if not acao:
        raise SystemExit("Uso: python -m src.marketing divulgar|lista_black|lista_barata|lista_barata_agora|relatorio|teste|busca")
    acao()
