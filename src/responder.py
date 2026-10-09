"""Etapa 3 — Lê os comentários dos posts recentes e manda o link no direct de quem pediu.

Uso: python -m src.responder
"""
import json
import random
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta

from . import config, instagram
from .garimpar import BRT, FMT, agora, carregar_fila

ARQ_RESPONDIDOS = config.PASTA_DADOS / "respondidos.json"
DIAS_JANELA = 7                 # o Instagram só aceita resposta privada até 7 dias após o comentário
MAX_POR_EXECUCAO = 40
RESPOSTA_PUBLICA = True         # também responde no próprio comentário ("te mandei no direct")

GATILHO = re.compile(r"\b(eu\s*quero|quero|link|eu\s*quero\s*o\s*link|manda)\b")

DM_BOTAO = ("Oi! 😊 Aqui está a oferta {titulo} 👇\n"
            "Toque no botão para abrir a oferta ({loja}). Corre que preço de oferta muda rápido! 🛒\n"
            "(link de afiliado: você paga o mesmo e ajuda o Garimpo VIP)")
TITULO_BOTAO = "🛒 Ver oferta"
NOME_LOJA = {"shopee": "Shopee", "aliexpress": "AliExpress"}

# Plano B, se o Instagram recusar o botão
DM = ("Oi! 😊 Aqui está o link da oferta {titulo} 👇\n{link}\n\n"
      "Corre que preço de oferta muda rápido! 🛒\n"
      "(link de afiliado — você paga o mesmo e ajuda o Garimpo VIP a continuar garimpando)")

PUBLICAS = ["Te mandei no direct! 📩", "Enviado no seu direct! 💌", "Já está no seu direct! 😉",
            "Confere o direct, te mandei o link! 📲", "Link enviado no direct! 🛍️"]


def _normalizar(txt):
    txt = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return txt.lower()


def pediu_link(texto):
    return bool(GATILHO.search(_normalizar(texto)))


def carregar_respondidos():
    if ARQ_RESPONDIDOS.exists():
        return json.loads(ARQ_RESPONDIDOS.read_text(encoding="utf-8"))
    return {}


def salvar_respondidos(dados):
    limite = (agora() - timedelta(days=DIAS_JANELA + 3)).strftime(FMT)
    dados = {k: v for k, v in dados.items() if v.get("em", "") >= limite}
    ARQ_RESPONDIDOS.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def posts_ativos(fila):
    limite = agora() - timedelta(days=DIAS_JANELA)
    return [o for o in fila["ofertas"].values()
            if o.get("status") == "postado" and o.get("id_post") and o.get("postado_em")
            and datetime.strptime(o["postado_em"], FMT).replace(tzinfo=BRT) >= limite]


def responder(api=instagram):
    if not api.tem_token():
        print("⏸️  IG_ACCESS_TOKEN ainda não configurado — respostas em espera.")
        return -1
    fila = carregar_fila()
    posts = posts_ativos(fila)
    if not posts:
        print("Nenhum post nos últimos 7 dias.")
        return -1
    minha = api.conta()
    respondidos = carregar_respondidos()
    enviados = falhas = 0
    for o in posts:
        try:
            coms = api.comentarios(o["id_post"])
        except Exception as e:
            print(f"⚠️  Comentários do post {o['id_post']}: {e}")
            continue
        for c in coms:
            cid = c["id"]
            autor = (c.get("from") or {}).get("id")
            if cid in respondidos or autor == minha["user_id"] or c.get("username") == minha.get("username"):
                continue
            if not pediu_link(c.get("text", "")):
                continue
            usuario = c.get("username") or (c.get("from") or {}).get("username", "")
            ja_recebeu = any(r.get("post") == o["id_post"] and r.get("dm") == "ok" and autor
                             and r.get("autor") == autor for r in respondidos.values())
            if ja_recebeu:
                respondidos[cid] = {"post": o["id_post"], "oferta": o["id"], "usuario": usuario,
                                    "autor": autor, "em": agora().strftime(FMT), "dm": "repetido"}
                continue
            if enviados >= MAX_POR_EXECUCAO:
                break
            reg = {"post": o["id_post"], "oferta": o["id"], "usuario": usuario,
                   "autor": autor, "em": agora().strftime(FMT)}
            try:
                try:
                    api.resposta_privada_botao(minha["user_id"], cid, DM_BOTAO.format(titulo=o["titulo"], loja=NOME_LOJA.get(o.get("plataforma") or "shopee", "loja")),
                                               o["link_afiliado"], TITULO_BOTAO)
                    reg["formato"] = "botao"
                except Exception as e:
                    print(f"   (botão recusado: {e}; enviando como texto)")
                    api.resposta_privada(minha["user_id"], cid,
                                         DM.format(titulo=o["titulo"], link=o["link_afiliado"]))
                    reg["formato"] = "texto"
                reg["dm"] = "ok"
                enviados += 1
                if RESPOSTA_PUBLICA:
                    try:
                        api.responder_comentario(cid, random.choice(PUBLICAS))
                    except Exception as e:
                        print(f"   (resposta pública falhou: {e})")
                print(f"📩 Link enviado para @{reg['usuario']} — {o['titulo']}")
            except Exception as e:
                falhas += 1
                reg["dm"] = f"erro: {str(e)[:200]}"
                print(f"⚠️  DM para @{reg['usuario']} falhou: {e}")
            respondidos[cid] = reg
            time.sleep(2)
    salvar_respondidos(respondidos)
    print(f"🏁 {enviados} links enviados, {falhas} falhas, {len(posts)} posts verificados.")
    return enviados


if __name__ == "__main__":
    try:
        # O aviso da Meta (webhook) às vezes chega antes de o comentário aparecer na API:
        # se nada foi enviado, espera um pouco e confere de novo.
        if not responder():
            time.sleep(20)
            responder()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
