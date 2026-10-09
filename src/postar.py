"""Etapa 2 — Postagem no Instagram, em duas fases dentro do mesmo job do GitHub Actions:

  python -m src.postar preparar   → escolhe a oferta, gera foto ou Reels em site/ (vai para o GitHub Pages)
  python -m src.postar publicar   → com o site no ar, cria o post no Instagram e atualiza a fila

O formato alterna entre foto e Reels (ou force com FORMATO=foto|reels).
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

from . import config, facebook, imagem, instagram, reels, story, telegram, video_manual
from .garimpar import BRT, FMT, agora, carregar_fila, salvar_fila

PASTA_SITE = config.RAIZ / "site"
ARQ_PROXIMO = config.PASTA_PERFIL / "proximo.json"
MAX_TENTATIVAS = 2
# Cada post do feed vai também para o story (só no Garimpo VIP; desligue com STORIES=0)
STORIES = config.PERFIL == "garimpo" and os.getenv("STORIES", "1") != "0"


def _saida(chave, valor):
    arq = os.getenv("GITHUB_OUTPUT")
    if arq:
        with open(arq, "a") as f:
            f.write(f"{chave}={valor}\n")


def _validos(fila):
    limite = agora() - timedelta(days=config.DIAS_VALIDADE_PENDENTE)
    return [o for o in fila["ofertas"].values()
            if o.get("status") == "pendente"
            and datetime.strptime(o["criado_em"], FMT).replace(tzinfo=BRT) >= limite]


def _ultimos_postados(fila, n=3):
    post = [o for o in fila["ofertas"].values() if o.get("status") == "postado" and o.get("postado_em")]
    return sorted(post, key=lambda o: (o["postado_em"], o.get("postado_ts", 0)), reverse=True)[:n]


def candidatos_ordenados(fila):
    """Vídeo manual primeiro; depois Ouro (Prata só se faltar Ouro), evitando repetir categoria."""
    candidatos = sorted(_validos(fila), key=lambda o: o.get("pontos", 0), reverse=True)
    recentes = {o["categoria"] for o in _ultimos_postados(fila)}
    manuais = [o for o in candidatos if o.get("video_manual")]
    resto = [o for o in candidatos if not o.get("video_manual") and not o.get("so_telegram")
             and o["categoria"] in config.NICHO]   # categoria que passou para outra conta fica de fora
    # 💎 Achado escondido: entra junto com o Ouro, mas no máximo config.ACHADOS_POR_DIA por dia
    hoje = agora().strftime("%Y-%m-%d")
    achados_hoje = sum(1 for o in fila["ofertas"].values() if o.get("nivel") == "achado"
                       and str(o.get("postado_em") or "").startswith(hoje))
    pode_achado = achados_hoje < config.ACHADOS_POR_DIA
    ouro = [o for o in resto if o.get("nivel", "ouro") == "ouro"
            or (pode_achado and o.get("nivel") == "achado")]
    base = ouro or [o for o in resto if o.get("nivel") != "achado"] or resto
    return manuais + [o for o in base if o["categoria"] not in recentes] + \
        [o for o in base if o["categoria"] in recentes]


def formato_da_vez(fila):
    forcado = (os.getenv("FORMATO") or "").strip().lower()
    if forcado in ("foto", "reels"):
        return forcado
    ult = _ultimos_postados(fila, 1)
    return "foto" if ult and ult[0].get("formato") == "reels" else "reels"


def preparar():
    _saida("tem_post", "false")
    if not instagram.tem_token():
        print("⏸️  IG_ACCESS_TOKEN ainda não configurado — postagem em espera.")
        return
    fila = carregar_fila()
    if config.PERFIL == "garimpo":   # vídeos manuais (pasta videos/) são do Garimpo VIP
        try:
            video_manual.registrar_na_fila(fila)
        except Exception as e:
            print(f"::warning::Falha ao ler videos/: {e}")
    formato_padrao = formato_da_vez(fila)
    pasta = PASTA_SITE / "midia"
    pasta.mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    (PASTA_SITE / "index.html").write_text(f"<!doctype html><title>{config.NOME_MARCA}</title>{config.NOME_MARCA}")
    oferta = None
    forcada = (os.getenv("OFERTA_ID") or "").strip()
    lista = candidatos_ordenados(fila)
    if forcada:   # teste manual: posta exatamente esta oferta
        lista = [o for o in fila["ofertas"].values() if o["id"] == forcada and o.get("status") == "pendente"]
        if not lista:
            print(f"::warning::Oferta {forcada} não está pendente na fila.")
    for cand in lista[:3]:
        formato = "reels" if cand.get("video_manual") else formato_padrao
        nome = f"{cand['id']}-{int(time.time())}.{'mp4' if formato == 'reels' else 'jpg'}"
        try:
            if cand.get("video_manual"):
                video_manual.gerar_reels(cand, config.RAIZ / cand["video_manual"], pasta / nome)
                oferta = cand
                break
            foto = imagem._baixar_foto(cand["imagem"])
            if formato == "reels":
                reels.gerar(cand, pasta / nome, foto=foto)
            else:
                imagem.gerar(cand, pasta / nome, foto=foto)
            oferta = cand
            break
        except Exception as e:
            print(f"⚠️  Falha ao preparar {cand['id']} ({e}); tentando a próxima.")
            cand["tentativas"] = cand.get("tentativas", 0) + 1
            cand["ultimo_erro"] = str(e)[:300]
            if cand["tentativas"] >= MAX_TENTATIVAS:
                cand["status"] = "erro"
    salvar_fila(fila)
    if not oferta:
        print("⚠️  Nenhuma oferta pendente válida na fila.")
        return
    prox = {"id": oferta["id"], "formato": formato, "arquivo": f"midia/{nome}"}
    if STORIES and formato == "foto":   # story vertical feito a partir da arte do feed
        try:
            story.gerar(pasta / nome, pasta / f"story-{nome}")
            prox["story"] = f"midia/story-{nome}"
        except Exception as e:
            print(f"::warning::Arte do story falhou: {e}")
    elif STORIES:
        prox["story"] = prox["arquivo"]   # o próprio Reels (já é vertical) vai para o story
    ARQ_PROXIMO.write_text(json.dumps(prox), encoding="utf-8")
    print(f"🎬 Preparado {formato}: {oferta['titulo']} (R$ {oferta['preco_fmt']}, {oferta['categoria']})")
    _saida("tem_post", "true")


def _esperar_url(url, limite_s=180):
    inicio = time.time()
    while time.time() - inicio < limite_s:
        try:
            if requests.head(url, timeout=20, allow_redirects=True).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(10)
    raise RuntimeError(f"A mídia não ficou acessível em {url}")


def publicar():
    prox = json.loads(ARQ_PROXIMO.read_text(encoding="utf-8"))
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PAGES_URL ausente — o GitHub Pages está ativado (Settings → Pages → GitHub Actions)?")
    url = f"{base}/{prox['arquivo']}"
    fila = carregar_fila()
    oferta = fila["ofertas"][prox["id"]]
    try:
        _esperar_url(url)
        ig_id = instagram.conferir_conta()["user_id"]
        if prox["formato"] == "reels":
            cont = instagram.criar_container(ig_id, oferta["legenda"], video_url=url)
        else:
            cont = instagram.criar_container(ig_id, oferta["legenda"], imagem_url=url)
        instagram.aguardar_container(cont)
        media_id = instagram.publicar(ig_id, cont)
    except Exception as e:
        oferta["tentativas"] = oferta.get("tentativas", 0) + 1
        oferta["ultimo_erro"] = str(e)[:300]
        if oferta["tentativas"] >= MAX_TENTATIVAS:
            oferta["status"] = "erro"
        salvar_fila(fila)
        ARQ_PROXIMO.unlink(missing_ok=True)
        raise
    if oferta.get("video_manual"):
        video_manual.baixar_da_pasta(oferta)
    oferta.update({"status": "postado", "id_post": media_id, "formato": prox["formato"],
                   "postado_em": agora().strftime(FMT), "postado_ts": time.time(), "permalink": instagram.permalink(media_id)})
    salvar_fila(fila)
    ARQ_PROXIMO.unlink(missing_ok=True)
    print(f"✅ Publicado ({prox['formato']}): {oferta['titulo']} → {oferta['permalink'] or media_id}")
    if prox.get("story"):
        try:
            surl = f"{base}/{prox['story']}"
            eh_video = prox["story"].endswith(".mp4")
            _esperar_url(surl)
            cont_s = instagram.criar_story(ig_id, video_url=surl if eh_video else None,
                                           imagem_url=None if eh_video else surl)
            instagram.aguardar_container(cont_s)
            instagram.publicar(ig_id, cont_s)
            oferta["story"] = "ok"
            print("📲 Também publicado no story.")
        except Exception as e:
            oferta["story"] = f"erro: {str(e)[:200]}"
            print(f"::warning::Story falhou: {e}")
        salvar_fila(fila)
    if config.TELEGRAM_ATIVO and telegram.configurado() and oferta.get("telegram") != "ok":
        try:
            telegram.enviar_oferta(oferta, PASTA_SITE / prox["arquivo"], prox["formato"])
            oferta["telegram"] = "ok"
            print("📣 Enviado ao canal do Telegram.")
        except Exception as e:
            oferta["telegram"] = f"erro: {str(e)[:200]}"
            print(f"::warning::Telegram falhou: {e}")
        salvar_fila(fila)
    if config.PERFIL == "garimpo" and facebook.configurado() and not oferta.get("fb_post"):
        try:
            leg = legenda_facebook(oferta["legenda"])
            if prox["formato"] == "reels":
                pid = facebook.postar_video(url, leg)
            else:
                pid = facebook.postar_foto(url, leg)
            oferta["fb_post"] = pid
            print(f"📘 Publicado na página do Facebook ({pid}).")
        except Exception as e:
            oferta["fb_erro"] = str(e)[:300]
            print(f"::warning::Facebook falhou: {e}")
        salvar_fila(fila)


def legenda_facebook(leg):
    """No Facebook o link vai pelo Messenger, não pelo direct."""
    return leg.replace("no direct", "no Messenger").replace("no Direct", "no Messenger")


if __name__ == "__main__":
    fase = sys.argv[1] if len(sys.argv) > 1 else ""
    acao = {"preparar": preparar, "publicar": publicar}.get(fase)
    if not acao:
        print("Uso: python -m src.postar preparar|publicar")
        sys.exit(2)
    try:
        acao()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
