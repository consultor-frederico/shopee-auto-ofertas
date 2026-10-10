"""Rodada do canal do Telegram: manda as melhores ofertas da fila que ainda não foram para o canal.

Uso: python -m src.telegram_ofertas
O ritmo do Telegram é independente do Instagram (mais ofertas por dia).
"""
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import config, imagem, precos, telegram
from .garimpar import BRT, FMT, agora, carregar_fila, salvar_fila

POR_EXECUCAO = int(os.getenv("TELEGRAM_POR_EXECUCAO", "2"))


def candidatas(fila):
    limite = agora() - timedelta(days=config.DIAS_VALIDADE_PENDENTE)
    ofs = [o for o in fila["ofertas"].values()
           if o.get("status") in ("pendente", "postado") and o.get("telegram") != "ok"
           and o.get("link_afiliado") and o.get("titulo") and not o.get("video_manual")
           and datetime.strptime(o["criado_em"], FMT).replace(tzinfo=BRT) >= limite]
    ofs.sort(key=lambda o: o.get("pontos", 0), reverse=True)
    # alterna categorias: evita duas seguidas do mesmo nicho
    escolhidas, cats = [], set()
    for o in ofs:
        if len(escolhidas) >= POR_EXECUCAO:
            break
        if o["categoria"] not in cats:
            escolhidas.append(o)
            cats.add(o["categoria"])
    for o in ofs:
        if len(escolhidas) >= POR_EXECUCAO:
            break
        if o not in escolhidas:
            escolhidas.append(o)
    return escolhidas


def rodar():
    if not telegram.configurado():
        print("⏸️  Telegram ainda não configurado — em espera.")
        return
    fila = carregar_fila()
    ofs = candidatas(fila)
    if not ofs:
        print("Nenhuma oferta nova para o canal.")
        return
    pasta = Path(tempfile.mkdtemp())
    enviadas = 0
    for o in ofs:
        situacao = precos.conferir(o)
        if situacao in ("sumiu", "subiu"):
            o["telegram"] = "descartado"
            if o.get("status") == "pendente":
                o["status"] = "descartado"
            continue
        try:
            arte = pasta / f"{o['id']}.jpg"
            imagem.gerar(o, arte, foto=imagem._baixar_foto(o["imagem"]))
            telegram.enviar_oferta(o, arte, "foto")
            o["telegram"] = "ok"
            o["telegram_em"] = agora().strftime(FMT)
            enviadas += 1
            print(f"📣 {o['categoria']:<11} R$ {o['preco_fmt']:>8}  {o['titulo']}")
        except Exception as e:
            o["telegram_tentativas"] = o.get("telegram_tentativas", 0) + 1
            if o["telegram_tentativas"] >= 2:
                o["telegram"] = "erro"
            print(f"::warning::Telegram falhou para {o['id']}: {e}")
        time.sleep(3)
    salvar_fila(fila)
    print(f"🏁 {enviadas} ofertas enviadas ao canal.")


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
