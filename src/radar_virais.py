"""📡 Radar de virais: o que está bombando nas páginas de achadinhos vira busca do garimpo.

Uma vez por dia (por perfil), o robô:
  1. lê os posts recentes das páginas da lista data/radar_perfis.json pela API do Instagram
     (business_discovery: só contas profissionais públicas). Essa leitura só existe no login do
     Facebook: usa o token da Página (FB_PAGE_ID/FB_PAGE_TOKEN) e o Instagram ligado a ela, que só
     lê (serve para os dois perfis);
  2. ordena pelo engajamento (curtidas + 5x comentários: comentário costuma ser "QUERO");
  3. a IA lê a legenda de cada post campeão e traduz o produto em termos de busca genéricos,
     do jeito que o vendedor escreve na Shopee (sem marca, personagem ou celebridade);
  4. guarda os termos em <pasta do perfil>/radar.json. Cada rodada do garimpo gasta alguns
     (config.PALAVRAS_VIRAIS_POR_GARIMPO), antes das buscas da IA e das fixas.

Post já lido não volta. Sem token da Página ou sem IA, o radar só pula (o garimpo segue igual).

Teste: python -m src.radar_virais   (lê as páginas e mostra os termos, sem gravar nada)
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import config, legenda

BRT = timezone(timedelta(hours=-3))
ARQ_PERFIS = config.PASTA_DADOS / "radar_perfis.json"
ARQ_RADAR = config.PASTA_PERFIL / "radar.json"
DIAS_RECENTES = int(os.getenv("RADAR_DIAS", "10"))        # só posts desses últimos dias
POSTS_POR_DIA = int(os.getenv("RADAR_POSTS", "25"))       # campeões que a IA traduz por dia
POSTS_POR_PAGINA = int(os.getenv("RADAR_POSTS_PAGINA", "4"))  # nenhuma página domina o radar
TERMOS_POR_CATEGORIA = 2                                  # por rodada: o radar fica variado
PESO_COMENTARIO = 5

PROMPT = """Você ajuda a página de achadinhos {marca} (público: {publico}).
Abaixo estão posts que BOMBARAM em outras páginas de achadinhos do Instagram. Para cada um,
descubra qual é o produto físico e crie termos de busca para achá-lo na Shopee.

Regras dos termos:
- 2 a 4 palavras, do jeito que o VENDEDOR escreve no título do anúncio (a busca é literal);
- genéricos: NUNCA marca, personagem, celebridade, time ou franquia (ex.: "umidificador do
  Bob Marley" vira "umidificador estatueta" e "umidificador resina decorativo");
- 2 ou 3 termos por produto, do mais exato ao mais amplo.

Categoria: uma de {categorias}. Use "fora" se não for produto físico, se não combina com o
público, se for item de fumo/droga/arma/adulto, ou se não der para saber o que é.

Posts:
{posts}

Responda APENAS com JSON: {{"itens": [{{"i": 1, "produto": "...", "categoria": "...", "termos": ["...", "..."]}}]}}"""


def _hoje():
    return datetime.now(BRT).strftime("%Y-%m-%d")


def _limpo(t):
    return re.sub(r"\s+", " ", str(t or "")).strip().lower()


def perfis():
    try:
        dados = json.loads(ARQ_PERFIS.read_text(encoding="utf-8"))
    except Exception:
        return []
    lista = dados.get(config.PERFIL, []) if isinstance(dados, dict) else dados
    return list(dict.fromkeys(str(u).lstrip("@").strip() for u in lista if str(u).strip()))


def carregar():
    try:
        dados = json.loads(ARQ_RADAR.read_text(encoding="utf-8"))
    except Exception:
        dados = {}
    dados.setdefault("vistos", {})
    dados.setdefault("termos", [])
    return dados


def salvar(dados):
    limite = (datetime.now(BRT) - timedelta(days=60)).strftime("%Y-%m-%d")
    dados["vistos"] = {k: v for k, v in dados["vistos"].items() if v >= limite}
    dados["termos"] = [t for t in dados["termos"] if t.get("dia", "") >= limite][-300:]
    ARQ_RADAR.parent.mkdir(parents=True, exist_ok=True)
    ARQ_RADAR.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


API = "https://graph.facebook.com/v23.0"


def _token():
    return (os.getenv("FB_PAGE_TOKEN") or "").strip() if (os.getenv("FB_PAGE_ID") or "").strip() else ""


def _get(token, caminho, campos):
    r = requests.get(f"{API}/{caminho}", params={"fields": campos, "access_token": token}, timeout=60)
    corpo = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in corpo:
        raise RuntimeError(f"HTTP {r.status_code}: {str((corpo.get('error') or {}).get('message', '?'))[:160]}")
    return corpo


def posts_em_alta(token):
    """Posts recentes de cada página da lista, do mais engajado para o menos."""
    corte = datetime.now(timezone.utc) - timedelta(days=DIAS_RECENTES)
    ig = (_get(token, os.getenv("FB_PAGE_ID").strip(), "instagram_business_account")
          .get("instagram_business_account") or {}).get("id")
    if not ig:
        raise RuntimeError("a Página do Facebook não tem Instagram profissional ligado")
    saida = []
    for usuario in perfis():
        campo = ("business_discovery.username(%s){username,followers_count,"
                 "media.limit(40){caption,like_count,comments_count,timestamp,permalink,media_type}}" % usuario)
        try:
            d = _get(token, ig, campo)["business_discovery"]
        except Exception as e:
            print(f"   📡 @{usuario}: sem dado ({str(e)[:120]})")
            continue
        midias = (d.get("media") or {}).get("data") or []
        n = 0
        for m in midias:
            quando = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            if quando < corte or not (m.get("caption") or "").strip():
                continue
            curtidas, coments = int(m.get("like_count") or 0), int(m.get("comments_count") or 0)
            saida.append({"perfil": d.get("username", usuario), "permalink": m.get("permalink"),
                          "legenda": m["caption"].strip(), "curtidas": curtidas, "comentarios": coments,
                          "nota": curtidas + PESO_COMENTARIO * coments})
            n += 1
        print(f"   📡 @{d.get('username', usuario)}: {d.get('followers_count', '?')} seguidores, "
              f"{n} posts nos últimos {DIAS_RECENTES} dias")
    saida.sort(key=lambda p: -p["nota"])
    return saida


def traduzir(posts):
    """[{produto, categoria, termos}] para cada post (mesma ordem; None quando a IA pula)."""
    if not posts or not config.GROQ_API_KEY:
        return []
    texto = "\n".join(f"{i}. ({p['curtidas']} curtidas, {p['comentarios']} comentários) "
                      f"{re.sub(r'\\s+', ' ', p['legenda'])[:450]}" for i, p in enumerate(posts, 1))
    prompt = PROMPT.format(marca=config.NOME_MARCA, publico=config.PUBLICO,
                           categorias=", ".join(config.NICHO), posts=texto)
    try:
        bruto = legenda._chamar_groq(prompt)
        itens = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("itens") or []
    except Exception as e:
        print(f"⚠️  Radar: a IA não traduziu os posts ({e})")
        return []
    por_i = {int(it.get("i", 0)): it for it in itens if isinstance(it, dict)}
    saida = []
    for i in range(1, len(posts) + 1):
        it = por_i.get(i) or {}
        cat = it.get("categoria")
        termos = [_limpo(t) for t in it.get("termos") or []]
        termos = [t for t in termos if 2 <= len(t.split()) <= 4 and 5 <= len(t) <= 40
                  and not any(p in t for p in config.PALAVRAS_PROIBIDAS)]
        saida.append({"produto": it.get("produto", ""), "categoria": cat, "termos": termos}
                     if cat in config.NICHO and termos else None)
    return saida


def atualizar(dados, gravar=True):
    """Lê as páginas (uma vez por dia) e acrescenta os termos novos. Devolve quantos entraram."""
    token = _token()
    if not token or not perfis():
        return 0
    hoje = _hoje()
    if gravar and dados.get("dia") == hoje:
        return 0
    print("📡 Radar de virais: lendo as páginas de achadinhos")
    novos, por_pagina = [], {}
    for p in posts_em_alta(token):
        if p["permalink"] in dados["vistos"] or por_pagina.get(p["perfil"], 0) >= POSTS_POR_PAGINA:
            continue
        por_pagina[p["perfil"]] = por_pagina.get(p["perfil"], 0) + 1
        novos.append(p)
    novos = novos[:POSTS_POR_DIA]
    traducoes = traduzir(novos)
    ja = {_limpo(t["termo"]) for t in dados["termos"]}
    n = 0
    for p, tr in zip(novos, traducoes):
        dados["vistos"][p["permalink"]] = hoje
        if not tr:
            print(f"   ⏭️  pulado: {p['legenda'][:70]!r}")
            continue
        print(f"   🔥 {p['curtidas']} curtidas / {p['comentarios']} coments (@{p['perfil']}): "
              f"{tr['produto']} → {', '.join(tr['termos'])}")
        for termo in tr["termos"]:
            if termo not in ja:
                ja.add(termo)
                dados["termos"].append({"termo": termo, "cat": tr["categoria"], "produto": tr["produto"],
                                        "nota": p["nota"], "perfil": p["perfil"],
                                        "permalink": p["permalink"], "dia": hoje})
                n += 1
    dados["dia"] = hoje
    return n


def termos_para_rodada(n):
    """Até n (categoria, termo) do radar ainda não usados, dos posts mais engajados primeiro.
    Marca como usados e grava. Qualquer erro: devolve [] (o garimpo segue sem o radar)."""
    if n <= 0:
        return []
    try:
        dados = carregar()
        novos = atualizar(dados)
        if novos:
            print(f"📡 Radar: {novos} termos novos dos virais")
        livres = sorted((t for t in dados["termos"] if not t.get("usado") and t.get("cat") in config.NICHO),
                        key=lambda t: -t.get("nota", 0))
        from . import variedade
        hoje = _hoje()
        # variedade: cada produto viral é buscado 1 vez por dia (não volta com outro termo na rodada
        # seguinte), cada família (ex.: "umidificador") também, e no máximo 2 termos por categoria
        produtos = {t["produto"] for t in dados["termos"] if t.get("usado") == hoje}
        familias = {variedade.familia(p) for p in produtos}
        escolha, por_cat = [], {}
        for t in livres:
            fam = variedade.familia(t["produto"])
            if (t["produto"] in produtos or fam in familias
                    or por_cat.get(t["cat"], 0) >= TERMOS_POR_CATEGORIA):
                continue
            produtos.add(t["produto"])
            familias.add(fam)
            por_cat[t["cat"]] = por_cat.get(t["cat"], 0) + 1
            t["usado"] = hoje
            escolha.append((t["cat"], t["termo"]))
            if len(escolha) >= n:
                break
        salvar(dados)
        return escolha
    except Exception as e:
        print(f"⚠️  Radar de virais falhou ({str(e)[:200]}) — seguindo sem ele.")
        return []


if __name__ == "__main__":
    d = {"vistos": {}, "termos": []}
    print(f"Perfil {config.PERFIL}: páginas {perfis()}")
    if not _token():
        print("⏸️  Sem FB_PAGE_ID/FB_PAGE_TOKEN neste ambiente.")
    else:
        print(f"Termos novos: {atualizar(d, gravar=False)}")
