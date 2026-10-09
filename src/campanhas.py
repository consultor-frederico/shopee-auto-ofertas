"""Vigia de campanhas/cupons da Shopee: quando a API libera uma campanha nova, publica no Telegram.

Uso: python -m src.campanhas
A API de afiliados devolve sempre ~30 páginas fixas de categoria (offerType 2, sem data de fim);
essas são ignoradas. Qualquer outra oferta (campanha com período, cupons, datas como 11.11) é novidade.
"""
import html
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from . import config, shopee, telegram

ARQ = config.PASTA_DADOS / "campanhas.json"
BRT = timezone(timedelta(hours=-3))
ANO_LIMITE = 2100  # data de fim depois disso = página permanente
MAX_POR_RODADA = 3  # não inunda o canal se a Shopee liberar muitas campanhas de uma vez
CAMPOS = "offerName offerType offerLink originalLink imageUrl periodStartTime periodEndTime collectionId"


def _carregar():
    if ARQ.exists():
        return json.loads(ARQ.read_text(encoding="utf-8"))
    return {"vistas": {}}


def _salvar(d):
    ARQ.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _data(ts):
    try:
        return datetime.fromtimestamp(int(ts), BRT)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def eh_campanha(no):
    fim = _data(no.get("periodEndTime"))
    permanente = fim is None or fim.year >= ANO_LIMITE
    return not (str(no.get("offerType")) == "2" and permanente)


def buscar_todas():
    nos, pagina = [], 1
    while pagina <= 10:
        d = shopee.consultar("query{shopeeOfferV2(sortType:1,page:%d,limit:50){nodes{%s}}}" % (pagina, CAMPOS))
        parte = (d.get("shopeeOfferV2") or {}).get("nodes") or []
        nos += parte
        if len(parte) < 50:
            break
        pagina += 1
    return nos


def _chave(no):
    return f"{no.get('collectionId') or ''}|{no.get('offerName') or ''}|{no.get('periodStartTime') or ''}"


def _texto(no, ultimas_horas=False):
    nome = html.escape((no.get("offerName") or "Campanha Shopee").strip(" -"))
    fim = _data(no.get("periodEndTime"))
    titulo = "⏰ <b>ÚLTIMAS HORAS!</b>" if ultimas_horas else "🎟️ <b>CUPONS E OFERTAS NA SHOPEE</b>"
    linhas = [titulo, "", f"🔥 <b>{nome}</b>"]
    if fim and fim.year < ANO_LIMITE:
        linhas.append(f"📅 Válido até {fim.strftime('%d/%m às %Hh%M')}")
    linhas += ["", "Toque no botão para ver os cupons e as ofertas da campanha 👇",
               "", "<i>Link de afiliado: você paga o mesmo e ajuda o Garimpo VIP 💛</i>"]
    return "\n".join(linhas)


def _publicar(no, ultimas_horas=False):
    teclado = json.dumps({"inline_keyboard": [[{"text": "🎟️ Ver cupons e ofertas", "url": no["offerLink"]}]]})
    dados = {"chat_id": os.getenv("TELEGRAM_CHAT_ID").strip(), "parse_mode": "HTML",
             "reply_markup": teclado}
    if no.get("imageUrl"):
        try:
            img = requests.get(no["imageUrl"], timeout=30).content
            return telegram._api("sendPhoto", data=dict(dados, caption=_texto(no, ultimas_horas)),
                                 files={"photo": ("campanha.jpg", img)})
        except Exception as e:
            print(f"⚠️  Sem imagem da campanha ({e}); enviando só texto.")
    return telegram._api("sendMessage", data=dict(dados, text=_texto(no, ultimas_horas)))


def rodar():
    if not telegram.configurado():
        print("⏸️  Telegram não configurado — vigia de campanhas em espera.")
        return
    reg = _carregar()
    agora = datetime.now(BRT)
    campanhas = [n for n in buscar_todas() if eh_campanha(n) and n.get("offerLink")]
    print(f"🔎 Campanhas ativas na API: {len(campanhas)}")
    novas = alertas = 0
    for no in campanhas:
        k = _chave(no)
        visto = reg["vistas"].get(k)
        fim = _data(no.get("periodEndTime"))
        if not visto:
            if novas >= MAX_POR_RODADA:
                continue  # fica para a próxima rodada
            _publicar(no)
            reg["vistas"][k] = {"nome": no.get("offerName"), "publicada_em": agora.isoformat(),
                                "fim": fim.isoformat() if fim else "", "alerta_fim": False}
            novas += 1
            print(f"🎟️ Nova campanha publicada: {no.get('offerName')}")
            time.sleep(3)
        elif fim and not visto.get("alerta_fim") and timedelta(0) < fim - agora <= timedelta(hours=12):
            _publicar(no, ultimas_horas=True)
            visto["alerta_fim"] = True
            alertas += 1
            print(f"⏰ Alerta de últimas horas: {no.get('offerName')}")
            time.sleep(3)
    # esquece campanhas encerradas há mais de 30 dias
    limite = (agora - timedelta(days=30)).isoformat()
    reg["vistas"] = {k: v for k, v in reg["vistas"].items() if not v.get("fim") or v["fim"] >= limite}
    reg["ultima_verificacao"] = agora.isoformat()
    reg["ativas"] = len(campanhas)
    _salvar(reg)
    print(f"🏁 {novas} novas campanhas, {alertas} alertas de fim.")


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
