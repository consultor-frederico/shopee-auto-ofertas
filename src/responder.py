"""Etapa 3 — Lê os comentários dos posts recentes e manda o link no direct de quem pediu.

Uso: python -m src.responder
"""
import json
import os
import random
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta

from . import config, facebook, instagram, youtube
from .garimpar import BRT, FMT, agora, carregar_fila

ARQ_RESPONDIDOS = config.PASTA_PERFIL / "respondidos.json"
DIAS_JANELA = 7                 # o Instagram só aceita resposta privada até 7 dias após o comentário
MAX_POR_EXECUCAO = 40
RESPOSTA_PUBLICA = True         # também responde no próprio comentário ("te mandei no direct")

GATILHO = re.compile(r"\b(eu\s*quero|quero|link|eu\s*quero\s*o\s*link|manda)\b")

DM_BOTAO = ("Oi! 😊 Aqui está a oferta {titulo} 👇\n"
            "Toque no botão para abrir a oferta ({loja}). Corre que preço de oferta muda rápido! 🛒\n"
            f"(link de afiliado: você paga o mesmo e ajuda a página {config.NOME_MARCA})")
TITULO_BOTAO = "🛒 Ver oferta"
NOME_LOJA = {"shopee": "Shopee", "aliexpress": "AliExpress"}

# Plano B, se o Instagram recusar o botão
DM = ("Oi! 😊 Aqui está o link da oferta {titulo} 👇\n{link}\n\n"
      "Corre que preço de oferta muda rápido! 🛒\n"
      f"(link de afiliado — você paga o mesmo e ajuda a página {config.NOME_MARCA} a continuar garimpando)")

PUBLICAS = ["Te mandei no direct! 📩", "Enviado no seu direct! 💌", "Já está no seu direct! 😉",
            "Confere o direct, te mandei o link! 📲", "Link enviado no direct! 🛍️"]

PUBLICAS_FB = ["Te mandei no Messenger! 📩", "Enviado no seu Messenger! 💌", "Confere o Messenger, te mandei o link! 📲"]

if config.PERFIL == "ana":   # a Ana fala do jeito dela (contas independentes)
    DM_BOTAO = ("Oiê! 💚 Separei pra você: {titulo} ✨\n"
                "É só tocar no botão pra ver na {loja}. Corre que achadinho bom acaba rápido!\n"
                "(link de afiliada: você paga o mesmo e apoia a Ana Novo Achados)")
    TITULO_BOTAO = "💚 Quero ver"
    DM = ("Oiê! 💚 Separei pra você: {titulo} ✨\n{link}\n\n"
          "Corre que achadinho bom acaba rápido!\n"
          "(link de afiliada: você paga o mesmo e apoia a Ana Novo Achados)")
    PUBLICAS = ["Corre no direct, te mandei! 💚", "Mandei no seu direct ✨", "Tá no seu direct, amore! 💌",
                "Link enviado no direct 💚", "Olha o direct! ✨"]


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
    minha = None
    if config.PERFIL == "garimpo" and api is instagram:   # quadro "Você pediu, o Zé achou"
        try:
            from . import pedidos
            minha = api.conferir_conta()
            n = pedidos.coletar(api, minha)
            if n:
                print(f"🙋 {n} pedidos novos nos posts do Zé.")
        except Exception as e:
            print(f"::warning::Pedidos do Zé falharam: {e}")
    if not posts:
        print("Nenhum post nos últimos 7 dias.")
        return -1
    minha = minha or (api.conferir_conta() if hasattr(api, "conferir_conta") else api.conta())
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
                        reg["publica"] = "ok"
                    except Exception as e:
                        reg["publica"] = f"erro: {str(e)[:300]}"
                        print(f"::warning::Resposta pública falhou: {e}")
                print(f"📩 Link enviado para @{reg['usuario']} — {o['titulo']}")
            except Exception as e:
                falhas += 1
                reg["dm"] = f"erro: {str(e)[:200]}"
                print(f"⚠️  DM para @{reg['usuario']} falhou: {e}")
            respondidos[cid] = reg
            time.sleep(2)
    if config.PERFIL == "garimpo" and facebook.configurado():
        try:
            enviados += responder_facebook(posts, respondidos)
        except Exception as e:
            print(f"::warning::Respostas no Facebook falharam: {e}")
    if config.PERFIL == "garimpo" and youtube.configurado():
        try:
            enviados += responder_youtube(respondidos)
        except Exception as e:
            aviso = (" → falta o escopo youtube.force-ssl no YT_REFRESH_TOKEN"
                     if "insufficient" in str(e).lower() else "")
            print(f"::warning::Respostas no YouTube falharam{aviso}: {e}")
    salvar_respondidos(respondidos)
    print(f"🏁 {enviados} links enviados, {falhas} falhas, {len(posts)} posts verificados.")
    return enviados


def responder_facebook(posts, respondidos):
    """Mesmo esquema do Instagram, nos comentários dos posts da página: link pelo Messenger."""
    pagina = (os.getenv("FB_PAGE_ID") or "").strip()
    enviados = 0
    for o in posts:
        if not o.get("fb_post"):
            continue
        try:
            coms = facebook.comentarios(o["fb_post"])
        except Exception as e:
            print(f"⚠️  Comentários do Facebook {o['fb_post']}: {e}")
            continue
        for c in coms:
            cid = f"fb_{c['id']}"
            autor = (c.get("from") or {}).get("id")
            if cid in respondidos or autor == pagina or not pediu_link(c.get("message", "")):
                continue
            nome = (c.get("from") or {}).get("name", "")
            reg = {"post": o["fb_post"], "oferta": o["id"], "usuario": nome, "autor": autor,
                   "em": agora().strftime(FMT), "rede": "facebook"}
            if autor and any(r.get("post") == o["fb_post"] and r.get("dm") == "ok" and r.get("autor") == autor
                             for r in respondidos.values()):
                respondidos[cid] = dict(reg, dm="repetido")
                continue
            loja = NOME_LOJA.get(o.get("plataforma") or "shopee", "loja")
            try:
                try:
                    facebook.resposta_privada_botao(c["id"], DM_BOTAO.format(titulo=o["titulo"], loja=loja),
                                                    o["link_afiliado"], TITULO_BOTAO)
                    reg["formato"] = "botao"
                except Exception as e:
                    print(f"   (botão recusado no Facebook: {e}; enviando como texto)")
                    facebook.resposta_privada(c["id"], DM.format(titulo=o["titulo"], link=o["link_afiliado"]))
                    reg["formato"] = "texto"
                reg["dm"] = "ok"
                enviados += 1
                try:
                    facebook.responder_comentario(c["id"], random.choice(PUBLICAS_FB))
                    reg["publica"] = "ok"
                except Exception as e:
                    reg["publica"] = f"erro: {str(e)[:300]}"
                print(f"📘 Link enviado no Messenger para {nome} — {o['titulo']}")
            except Exception as e:
                reg["dm"] = f"erro: {str(e)[:200]}"
                print(f"::warning::Messenger para {nome} falhou: {e}")
            respondidos[cid] = reg
            time.sleep(2)
    return enviados


# No YouTube não existe direct: a resposta vai no próprio comentário, com o link da oferta.
RESPOSTA_YT = ("Oi, {nome}! 😊 Aqui está o link do {titulo} 👉 {link}\n"
               "Corre que preço de oferta muda rápido! Todos os achados também no Telegram: t.me/garimpovipofertas\n"
               f"(link de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")


def responder_youtube(respondidos):
    from .garimpar import carregar_fila
    por_video = {o["yt_video"]: o for o in carregar_fila()["ofertas"].values() if o.get("yt_video")}
    if not por_video:
        return 0
    enviados = 0
    for c in youtube.comentarios_recentes():
        cid = f"yt_{c['id']}"
        o = por_video.get(c["video"])
        if (not o or cid in respondidos or c["autor_canal"] == youtube.CANAL_ID
                or not pediu_link(c["texto"]) or not o.get("link_afiliado")):
            continue
        reg = {"post": c["video"], "oferta": o["id"], "usuario": c["autor"], "autor": c["autor_canal"],
               "em": agora().strftime(FMT), "rede": "youtube"}
        nome = (c["autor"] or "").lstrip("@").split()[0] if c["autor"] else "tudo bem"
        try:
            youtube.responder_comentario(c["id"], RESPOSTA_YT.format(nome=nome, titulo=o.get("titulo", "produto"),
                                                                   link=o["link_afiliado"]))
            reg["dm"] = "ok"
            enviados += 1
            print(f"▶️  Link respondido no YouTube para {c['autor']} — {o.get('titulo')}")
        except Exception as e:
            reg["dm"] = f"erro: {str(e)[:200]}"
            print(f"::warning::Resposta no YouTube para {c['autor']} falhou: {e}")
        respondidos[cid] = reg
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
