"""Kit do Canal do WhatsApp: o WhatsApp não tem API para postar em canais, então o robô
prepara a oferta e manda no Telegram PRIVADO do Fred. Lá chegam a arte e o texto já no
formato do WhatsApp, com um botão "Mandar no WhatsApp" que abre o WhatsApp com o texto pronto.

Uso: python -m src.whatsapp_kit
Segredos: TELEGRAM_BOT_TOKEN (o mesmo bot do canal) e TELEGRAM_CHAT_PRIVADO (o seu chat com o bot).
Se TELEGRAM_CHAT_PRIVADO ainda não existir, a rodada mostra no log o número do seu chat
(mande qualquer mensagem para o bot antes).
"""
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from . import config, curadoria, imagem, marcas, precos, telegram, vendas
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


DIAS_CANAL = int(os.getenv("WHATSAPP_DIAS_CANAL", "7"))   # janela de ofertas analisadas para o canal
LOTE_ANALISE = int(os.getenv("WHATSAPP_LOTE_ANALISE", "20"))   # quantas ofertas a IA avalia por rodada


def candidatas(fila):
    """Pool de ofertas ainda não analisadas para o canal, da mais promissora para a menos."""
    # o canal olha 7 dias de ofertas (as da grade normal), dando preferência às mais recentes
    limite = agora() - timedelta(days=DIAS_CANAL)
    ofs = [o for o in fila["ofertas"].values()
           if o.get("status") in ("pendente", "postado") and not o.get("whatsapp")
           and (o.get("plataforma") or "shopee") == "shopee"   # por enquanto, o canal só tem Shopee
           and o.get("link_afiliado") and o.get("titulo") and o.get("imagem") and not o.get("video_manual")
           and datetime.strptime(o["criado_em"], FMT).replace(tzinfo=BRT) >= limite]
    ofs.sort(key=lambda o: (o["criado_em"], o.get("pontos", 0)), reverse=True)
    return ofs[:LOTE_ANALISE]


def aprovadas(ofs, analise):
    """Só sai o que a análise do canal marcou como APROVADO. Repetidos/parecidos ficam de fora.
    REPROVADO e PENDENTE são marcados para não serem analisados de novo."""
    escolhidas = []
    for o in ofs:
        a = analise.get(str(o["id"]))
        if not a:
            continue
        o["whatsapp_analise"] = a
        if a["status"] == "REPROVADO":
            o["whatsapp"] = "reprovado"
        elif a["status"] == "PENDENTE":
            o["whatsapp"] = "pendente_analise"
        elif a["status"] == "APROVADO":
            if any(curadoria.parecido(o["nome"], e["nome"]) for e in escolhidas):
                o["whatsapp"] = "repetido"
                continue
            escolhidas.append(o)
    return escolhidas[:POR_EXECUCAO]


def texto_whatsapp(o):
    """Texto no formato do WhatsApp (*negrito*, ~riscado~, _itálico_)."""
    gancho = []
    for linha in (o.get("legenda") or "").splitlines():
        t = linha.strip()
        if not t or t.startswith(("#", "📲", "🔖", "🕒", "🏬")) or "QUERO" in t.upper() or "R$" in t:
            continue
        gancho.append(t.replace("*", ""))
    gancho = gancho[:2]
    apartir = "a partir de " if tem_variacoes(o) else ""
    preco = f"💰 {apartir}*R$ {o['preco_fmt']}*"
    if o.get("preco_de"):
        ligacao = "" if apartir else "por "   # "de ~R$ X~ a partir de *R$ Y*" (sem "por a partir de")
        preco = f"💰 de ~R$ {telegram._brl(o['preco_de'])}~ {ligacao}{apartir}*R$ {o['preco_fmt']}*"
        if o.get("desconto"):
            preco += f" (-{o['desconto']}%)"
    nota = (f"{o['avaliacao_pct']:.0f}% avaliações positivas" if o.get("avaliacao_pct")
            else f"nota {o.get('nota', 0):.1f}".replace(".", ","))
    vendidos = f"{o.get('vendas', 0):,}".replace(",", ".")   # não chamar de "vendas": apaga o módulo vendas
    loja = telegram.NOME_LOJA.get(plataforma(o), plataforma(o).title())
    partes = []
    if o.get("nivel") == "achado":
        partes += ["💎 *ACHADO ESCONDIDO*", ""]
    partes += [f"🔥 *{o['titulo'].replace('*', '')}*", ""]
    if gancho:
        partes += gancho + [""]
    prova = f"🏬 {marcas.texto_oficial(o)}" if marcas.eh_marca(o) else f"⭐ {nota} • {vendidos}+ vendidos"
    partes += [preco, prova, "",
               f"🛒 Compre na {loja}:", vendas.do_canal(o, "zap"), "",
               f"_{precos.aviso(o)}_",
               "_Link de afiliado: você paga o mesmo e ajuda o Garimpo VIP 💛_"]
    return "\n".join(partes)


PASTA_ZAP = config.PASTA_DADOS / "zap"   # arte + texto lidos pela página zap.html do site
PAGINA_ZAP = "https://consultor-frederico.github.io/shopee-auto-ofertas/zap.html?id="
DIAS_ZAP = 7


def guardar_zap(o, arte, texto):
    """Grava arte e texto para a página de compartilhar (um toque: foto + legenda no WhatsApp)."""
    PASTA_ZAP.mkdir(parents=True, exist_ok=True)
    limite = time.time() - DIAS_ZAP * 86400
    for velho in PASTA_ZAP.iterdir():
        if velho.stat().st_mtime < limite:
            velho.unlink()
    (PASTA_ZAP / f"{o['id']}.jpg").write_bytes(Path(arte).read_bytes())
    (PASTA_ZAP / f"{o['id']}.txt").write_text(texto, encoding="utf-8")


def enviar(o, arte):
    """A arte com a oferta na legenda e dois botões: 📲 Compartilhar (abre a página que manda
    foto + texto juntos para o WhatsApp; o "Copiar" do Telegram nunca leva a foto) e ✅ Aprovar."""
    chat = chat_privado()
    texto = texto_whatsapp(o)
    guardar_zap(o, arte, texto)
    if len(texto) > 1000:   # legenda do Telegram aceita até 1024: tira a descrição, mantém o aviso inteiro
        texto = texto_whatsapp(dict(o, legenda=""))
    texto = texto[:1000]
    compartilhar = {"text": "📲 Compartilhar no WhatsApp", "url": PAGINA_ZAP + str(o["id"])}
    aprovar = {"text": "✅ Aprovar", "callback_data": "ok:%s" % o["id"]}
    with open(arte, "rb") as f:
        telegram._api("sendPhoto", data={"chat_id": chat, "caption": texto,
                                         "reply_markup": json.dumps({"inline_keyboard": [[compartilhar], [aprovar]]})},
                      files={"photo": f})


def da_marca(fila, plat, qtd, ids=()):
    """Pega no feed da Awin as `qtd` melhores ofertas de uma marca (mais desconto, depois mais comissão)
    que ainda não foram para o WhatsApp, e põe na fila só para o kit (não entram no Instagram)."""
    from . import awin, legenda
    if plat not in marcas.MARCAS:
        print(f"::warning::Marca '{plat}' não cadastrada em src/marcas.py.")
        return []
    if not awin.configurado():
        print("::warning::Awin desligada (AWIN_ATIVO) ou sem o segredo AWIN_FEED_URL.")
        return []
    ja_foi = {k for k, o in fila["ofertas"].items() if o.get("whatsapp")}
    todas = [o for o in awin.produtos() if o["plataforma"] == plat and o["id"] not in ja_foi]
    todas.sort(key=lambda o: (o["desconto"], o["comissao"]), reverse=True)
    if ids:   # escolha manual pelo número do produto
        todas = [o for o in todas if o["id"] in ids]
        qtd = len(ids)
    if qtd <= 0:   # só lista no log, para escolher (não manda nada)
        capas = [o for o in todas if "capa" in o["nome"].lower() or "capinha" in o["nome"].lower()]
        com_desc = sum(1 for o in todas if o["desconto"] > 0)
        print(f"🔎 {len(todas)} produtos, {len(capas)} capas, {com_desc} com desconto")
        for o in capas[:50] + [o for o in todas if o not in capas][:30]:
            print(f"🔎 {o['id']}  R$ {o['preco_fmt']:>9}  -{o['desconto']}%  {o['categoria']:<10} {o['nome'][:90]}")
        return []
    escolhidas = []
    for o in todas:
        if len(escolhidas) >= qtd:
            break
        if any(curadoria.parecido(o["nome"], e["nome"]) for e in escolhidas):
            continue
        o = dict(o, uau=config.SHARK_UAU, nivel="ouro", origem_busca="whatsapp_manual",
                 pontos=config.SHARK_PONTOS, so_telegram=False)
        o.update({k: v for k, v in legenda.gerar(o).items() if k in ("titulo", "legenda")})
        o["status"] = "descartado"   # só o kit do WhatsApp: fica fora da fila do Instagram
        o["criado_em"] = agora().strftime(FMT)
        fila["ofertas"][o["id"]] = o
        escolhidas.append(o)
    print(f"🏬 {marcas.MARCAS[plat]['nome']}: {len(todas)} disponíveis, {len(escolhidas)} escolhidas para o WhatsApp.")
    return escolhidas


def rodar():
    if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        print("⏸️  Bot do Telegram não configurado — kit do WhatsApp em espera.")
        return
    if not chat_privado():
        print("⏸️  Falta o segredo TELEGRAM_CHAT_PRIVADO.")
        descobrir_chat()
        return
    fila = carregar_fila()
    forcada = (os.getenv("WHATSAPP_OFERTA") or "").strip()
    marca = (os.getenv("WHATSAPP_MARCA") or "").strip().lower().replace(" ", "")
    if marca:   # pedido manual: as N melhores de uma marca da Awin (ex.: vxcase)
        pasta = Path(tempfile.mkdtemp())
        ids = [i for i in forcada.replace(",", " ").split() if i]   # com marca, "oferta" aceita números do feed
        for o in da_marca(fila, marca, int(os.getenv("WHATSAPP_QTD") or "2"), ids):
            if precos.conferir(o) in ("sumiu", "subiu"):
                o["whatsapp"] = "descartado"
                continue
            arte = pasta / f"{o['id']}.jpg"
            imagem.gerar(o, arte, foto=imagem._baixar_foto(o["imagem"]))
            enviar(o, arte)
            o["whatsapp"] = "ok"
            o["whatsapp_em"] = agora().strftime(FMT)
            print(f"📲 {o['titulo']}  R$ {o['preco_fmt']}  (-{o['desconto']}%)")
            time.sleep(2)
        salvar_fila(fila)
        return
    if forcada:   # reenvio manual de uma oferta específica, no formato atual
        o = fila["ofertas"].get(forcada)
        if not o:
            print(f"::warning::Oferta {forcada} não encontrada na fila.")
            return
        situacao = precos.conferir(o)   # reenvio também confere o preço na loja antes de mandar
        if situacao in ("sumiu", "subiu"):
            print(f"::warning::Oferta {forcada} não enviada: o preço {situacao} na loja.")
            salvar_fila(fila)
            return
        pasta = Path(tempfile.mkdtemp())
        arte = pasta / f"{o['id']}.jpg"
        imagem.gerar(o, arte, foto=imagem._baixar_foto(o["imagem"]))
        enviar(o, arte)
        salvar_fila(fila)   # guarda o preço conferido
        print(f"📲 Reenviada: {o['id']} — {o.get('titulo', '')} (R$ {o['preco_fmt']})")
        return
    pool = candidatas(fila)
    if not pool:
        print("Nenhuma oferta nova para o WhatsApp.")
        return
    if os.getenv("WHATSAPP_TESTE") == "1":   # teste manual: manda a 1ª oferta sem a análise
        ofs = pool[:1]
        print("🧪 Modo teste: enviando a oferta de maior pontuação sem a análise do canal.")
    else:
        analise = curadoria.classificar_whatsapp(pool)
        if not analise:   # a IA não respondeu: avisa, para não passar a rodada sem perceber
            try:
                telegram._api("sendMessage", data={"chat_id": chat_privado(), "disable_web_page_preview": "true",
                              "text": "⚠️ Kit do WhatsApp: a análise dos critérios não respondeu nesta rodada. "
                                      "Nenhuma oferta automática foi enviada ao canal. Confira a chave da IA (GROQ)."})
            except Exception as e:
                print(f"::warning::Não consegui avisar a falha da análise: {e}")
        ofs = aprovadas(pool, analise)
        salvar_fila(fila)   # guarda as marcações de reprovado/pendente/repetido
    if not ofs:
        print(f"Nenhuma oferta aprovada para o canal nesta rodada ({len(analise)} analisadas).")
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
