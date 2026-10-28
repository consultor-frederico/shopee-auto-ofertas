"""Etapa 2 — Postagem no Instagram, em duas fases dentro do mesmo job do GitHub Actions:

  python -m src.postar preparar   → escolhe a oferta, gera foto ou Reels em site/ (vai para o GitHub Pages)
  python -m src.postar publicar   → com o site no ar, cria o post no Instagram e atualiza a fila

O formato: 2 Reels para cada foto (REELS_POR_FOTO; ou force com FORMATO=foto|reels|carrossel).
O último Reels antes de cada foto vira carrossel (capa + foto grande + "por que vale" e, no Garimpo,
o Zé em vídeo no fim); desligue com CARROSSEL=0.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

from . import aliexpress, carrossel, config, facebook, marcas, precos, imagem, instagram, legenda, reels, story, telegram, video_manual, youtube, ze, variedade, vitrine
from .garimpar import BRT, FMT, agora, carregar_fila, salvar_fila

PASTA_SITE = config.RAIZ / "site"
ARQ_PROXIMO = config.PASTA_PERFIL / "proximo.json"
MAX_TENTATIVAS = 2
# Desde 17/10/2026 o feed não tem mais post de oferta solta: as ofertas saem no carrossel de achados
# (src/achados.py, sempre abrindo com um vídeo do Zé ou da Ana). Aqui só saem os pedidos da Busca
# ("Você pediu, o Zé achou") e os vídeos manuais. SO_CARROSSEL=0 volta ao jeito antigo.
SO_CARROSSEL = os.getenv("SO_CARROSSEL", "1") != "0"
# Cada post do feed vai também para o story (desligue com STORIES=0).
# Na Ana o story tem visual próprio (layout_ana.gerar_story); desligue com ANA_STORIES=0.
ANA_STORIES = os.getenv("ANA_STORIES", "1") == "1"   # ligado em 13/10/2026
STORIES = (config.PERFIL == "garimpo" or ANA_STORIES) and os.getenv("STORIES", "1") != "0"


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
    pedidos_ze = [o for o in candidatos if o.get("pedido") and not o.get("video_manual")]
    manuais += pedidos_ze[:1]   # "Você pediu, o Zé achou": um por vez, na frente da fila
    preferidos = [o for o in candidatos if o.get("preferencial") and not o.get("video_manual")]   # aprovadas por você
    resto = [o for o in candidatos if not o.get("video_manual") and not o.get("so_telegram") and not o.get("pedido")
             and o["categoria"] in config.NICHO and variedade.diferenciado(o)]   # outra conta fica de fora; só produto diferenciado
    cheias = {p for p, n in marcas.hoje_por_marca(fila, "postado_em", agora().strftime("%Y-%m-%d")).items() if n >= config.SHARK_POR_DIA_INSTAGRAM}
    resto = [o for o in resto if o.get("plataforma") not in cheias]   # cada marca no máximo X por dia: não domina a página
    if not aliexpress.vagas_hoje(fila, "postado_em", config.ALIEXPRESS_POR_DIA_INSTAGRAM, agora().strftime("%Y-%m-%d")):
        resto = [o for o in resto if o.get("plataforma") != "aliexpress"]   # 🌎 internacional: no máximo 2 por dia
    # 💎 Achado escondido: entra junto com o Ouro, mas no máximo config.ACHADOS_POR_DIA por dia
    hoje = agora().strftime("%Y-%m-%d")
    achados_hoje = sum(1 for o in fila["ofertas"].values() if o.get("nivel") == "achado"
                       and str(o.get("postado_em") or "").startswith(hoje))
    pode_achado = achados_hoje < config.ACHADOS_POR_DIA
    ouro = [o for o in resto if o.get("nivel", "ouro") == "ouro"
            or (pode_achado and o.get("nivel") == "achado")]
    base = ouro or [o for o in resto if o.get("nivel") != "achado"] or resto
    fams = variedade.familias_recentes(fila, "postado_em")
    # Ouro só de família que saiu há pouco? Prata de outro tipo vence a repetição.
    if not any(variedade.familia(o) not in fams for o in base):
        base = [o for o in resto if o.get("nivel") != "achado" and variedade.familia(o) not in fams] or base
    base = [o for o in base if o["categoria"] not in recentes] + [o for o in base if o["categoria"] in recentes]
    # variedade: tipo de produto que saiu nas últimas HORAS_ENTRE_FAMILIA horas vai para o fim
    base = variedade.ordenar(base, fams)
    # 📡 veio do radar (bombando em outra página agora): passa na frente, até VIRAIS_NA_FRENTE_POR_DIA por dia
    virais_hoje = sum(1 for o in fila["ofertas"].values() if o.get("origem_busca") == "viral"
                      and str(o.get("postado_em") or "").startswith(hoje))
    if virais_hoje < config.VIRAIS_NA_FRENTE_POR_DIA:
        frente = [o for o in base if o.get("origem_busca") == "viral"
                  and o["categoria"] not in recentes and variedade.familia(o) not in fams]
        base = frente + [o for o in base if o not in frente]
    return manuais + preferidos + base


def formato_da_vez(fila):
    forcado = (os.getenv("FORMATO") or "").strip().lower()
    if forcado in ("foto", "reels", "carrossel"):
        return forcado
    # padrão: 2 Reels para cada foto (Reels é o que o Instagram mais mostra para quem não segue);
    # mude com REELS_POR_FOTO (1 = alterna foto e Reels)
    n = max(1, int(os.getenv("REELS_POR_FOTO", "2") or 2))
    ult = _ultimos_postados(fila, n)
    seguidos = 0
    for o in ult:
        if o.get("formato") not in ("reels", "carrossel"):
            break
        seguidos += 1
    if seguidos >= n:
        return "foto"
    # o último da sequência antes da foto vira carrossel: reels, carrossel, foto (1 em cada 3 posts)
    if (n >= 2 and seguidos == n - 1 and ult[0].get("formato") == "reels"
            and os.getenv("CARROSSEL", "1") != "0"):
        return "carrossel"
    return "reels"


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
    for fixo in (config.RAIZ / "assets" / "paginas").glob("*.html"):   # página inicial e privacidade
        (PASTA_SITE / fixo.name).write_text(fixo.read_text(encoding="utf-8"), encoding="utf-8")
    oferta = None
    forcada = (os.getenv("OFERTA_ID") or "").strip()
    lista = candidatos_ordenados(fila)
    if SO_CARROSSEL and not forcada:   # as ofertas saem no carrossel de achados (src/achados.py)
        lista = [o for o in lista if o.get("video_manual") or o.get("pedido")]
        if not lista:
            print("⏳ Sem pedido do Zé nem vídeo manual na fila: as ofertas saem no carrossel de achados.")
            return
    if forcada:   # teste manual: posta exatamente esta oferta
        lista = [o for o in fila["ofertas"].values() if o["id"] == forcada and o.get("status") == "pendente"]
        if not lista:
            print(f"::warning::Oferta {forcada} não está pendente na fila.")
    for cand in lista[:6]:
        situacao = precos.conferir(cand)
        if situacao in ("sumiu", "subiu"):
            cand["status"] = "descartado"
            cand["motivo"] = "produto fora do ar" if situacao == "sumiu" else "preço subiu desde o garimpo"
            print(f"🗑️  {cand.get('titulo')}: {cand['motivo']} — pulando.")
            continue
        formato = "reels" if cand.get("video_manual") else formato_padrao
        nome = f"{cand['id']}-{int(time.time())}.{'mp4' if formato == 'reels' else 'jpg'}"
        try:
            if cand.get("video_manual"):
                video_manual.gerar_reels(cand, config.RAIZ / cand["video_manual"], pasta / nome)
                _final_do_ze(pasta / nome, cand)
                oferta = cand
                break
            foto = imagem._baixar_foto(cand["imagem"])
            if formato == "reels":
                reels.gerar(cand, pasta / nome, foto=foto)
                _final_do_ze(pasta / nome, cand)
            elif formato == "carrossel":
                slides = [f"midia/{os.path.basename(a)}" for a in carrossel.gerar(cand, pasta / nome, foto=foto)]
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
    if config.PERFIL == "garimpo" and config.RAIO_X_ATIVO:   # 📊 Raio-X do Zé (nota, vendas e preço x parecidos)
        from . import raio_x
        raio_x.preparar(oferta)
        salvar_fila(fila)
    prox = {"id": oferta["id"], "formato": formato, "arquivo": f"midia/{nome}"}
    if formato == "carrossel":
        prox["slides"] = slides
    if STORIES and formato in ("foto", "carrossel"):   # story vertical feito da arte do feed (no carrossel, da capa)
        try:
            if config.PERFIL == "ana":
                from . import layout_ana
                layout_ana.gerar_story(pasta / nome, pasta / f"story-{nome}")
            else:
                story.gerar(pasta / nome, pasta / f"story-{nome}")
            prox["story"] = f"midia/story-{nome}"
        except Exception as e:
            print(f"::warning::Arte do story falhou: {e}")
    elif STORIES:
        prox["story"] = prox["arquivo"]   # o próprio Reels (já é vertical) vai para o story
    ARQ_PROXIMO.write_text(json.dumps(prox), encoding="utf-8")
    print(f"🎬 Preparado {formato}: {oferta['titulo']} (R$ {oferta['preco_fmt']}, {oferta['categoria']})")
    _saida("tem_post", "true")


def _final_do_ze(arquivo, oferta):
    """Vinheta do Zé Garimpo no fim do Reels; se falhar, o Reels sai sem ela."""
    try:
        oferta["final_ze"] = ze.emendar_final(arquivo, oferta) or ""
    except Exception as e:
        print(f"::warning::Vinheta do Zé não entrou ({e}); o Reels sai sem ela.")


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
    # ofertas garimpadas antes da linha "manda/salva" ganham a linha na hora de postar
    if oferta.get("legenda") and "📲" not in oferta["legenda"] and "🔖" not in oferta["legenda"]:
        corpo, _, tags = oferta["legenda"].partition("\n\n#")
        oferta["legenda"] = legenda.com_compartilhar(corpo, oferta) + (f"\n\n#{tags}" if tags else "")
    oferta["legenda"] = com_aviso(oferta.get("legenda") or "", oferta)
    if config.RAIO_X_ATIVO and oferta.get("raio_x"):
        from . import raio_x
        oferta["legenda"] = raio_x.com_raio_x(oferta["legenda"], oferta)
    try:
        _esperar_url(url)
        ig_id = instagram.conferir_conta()["user_id"]
        leg_ig = com_busca(oferta["legenda"], oferta)   # lembrete da Busca do Zé (só no Instagram)
        if prox["formato"] == "reels":
            cont = instagram.criar_container(ig_id, leg_ig, video_url=url)
        elif prox["formato"] == "carrossel":
            urls = [f"{base}/{s}" for s in prox["slides"]]
            for u in urls[1:]:
                _esperar_url(u)
            filhos = [instagram.criar_item_carrossel(ig_id, video_url=u) if u.endswith(".mp4")
                      else instagram.criar_item_carrossel(ig_id, imagem_url=u) for u in urls]
            for c in filhos:
                instagram.aguardar_container(c)
            cont = instagram.criar_carrossel(ig_id, filhos, leg_ig)
        else:
            cont = instagram.criar_container(ig_id, leg_ig, imagem_url=url)
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
    vitrine.gerar()
    print(f"✅ Publicado ({prox['formato']}): {oferta['titulo']} → {oferta['permalink'] or media_id}")
    if oferta.get("pedido"):
        from . import pedidos
        pedidos.entregar(oferta, ig_id)
        salvar_fila(fila)
    if prox.get("story"):
        try:
            surl = f"{base}/{prox['story']}"
            eh_video = prox["story"].endswith(".mp4")
            _esperar_url(surl)
            cont_s = instagram.criar_story(ig_id, video_url=surl if eh_video else None,
                                           imagem_url=None if eh_video else surl)
            instagram.aguardar_container(cont_s)
            oferta["story_id"] = instagram.publicar(ig_id, cont_s)   # para achar o produto quando responderem o story
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
    if (config.PERFIL == "garimpo" and prox["formato"] == "reels" and youtube.configurado()
            and not oferta.get("yt_video")):
        try:
            vid = youtube.enviar_short(PASTA_SITE / prox["arquivo"], oferta)
            oferta["yt_video"] = vid
            print(f"▶️  Publicado no YouTube Shorts: https://youtube.com/shorts/{vid}")
        except Exception as e:
            oferta["yt_erro"] = str(e)[:300]
            print(f"::warning::YouTube falhou: {e}")
        salvar_fila(fila)


def com_aviso(leg, oferta):
    """Põe (ou atualiza) a linha 🕒 do preço conferido logo antes das hashtags."""
    leg = "\n".join(l for l in leg.splitlines() if not l.startswith("🕒"))
    corpo, sep, tags = leg.partition("\n\n#")
    return f"{corpo.rstrip()}\n\n{precos.aviso(oferta)}" + (f"\n\n#{tags}" if sep else "")


LEMBRETES_BUSCA = [
    "🔎 Não era isso que você procurava? Comenta no post fixado que o Zé garimpa pra você!",
    "🔎 Procurando outra coisa? Fala pro Zé no post fixado do perfil (ou aqui no direct) que ele acha!",
    "🔎 Quer algo diferente? Manda no direct o que você procura que o Zé te traz os melhores achados!",
]
if config.PERFIL == "ana":
    LEMBRETES_BUSCA = [
        "💬 Procurando outra coisa? Comenta aqui o que você quer que eu acho pra você e te mando no direct!",
        "💬 Não era bem isso? Me fala nos comentários (ou no direct) o que você procura que eu encontro 💚",
        "💬 Quer algo diferente? Manda no meu direct o que você procura que eu te mando os melhores achadinhos!",
    ]
elif config.VALE_A_PENA_ATIVO:
    LEMBRETES_BUSCA.append("🤔 Viu um produto na Shopee e ficou na dúvida? Manda o link no direct que o Zé diz se vale a pena!")


def com_busca(leg, oferta):
    """Em 1 de cada 3 posts, lembra da Busca do Zé (antes das hashtags). Só no Garimpo VIP e
    só depois que o post fixo da Busca existe. Não vai para Facebook/YouTube/Telegram."""
    if config.PERFIL not in ("garimpo", "ana"):
        return leg
    try:
        from . import busca_ze
        if not busca_ze.carregar().get("ids"):
            return leg
    except Exception:
        return leg
    n = sum(map(ord, str(oferta.get("id", ""))))
    if n % 3:
        return leg
    corpo, sep, tags = leg.partition("\n\n#")
    return f"{corpo.rstrip()}\n\n{LEMBRETES_BUSCA[n // 3 % len(LEMBRETES_BUSCA)]}" + (f"\n\n#{tags}" if sep else "")


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
