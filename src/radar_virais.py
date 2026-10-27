"""📡 Radar de virais: o que está bombando nas páginas de achadinhos vira busca do garimpo.

Uma vez por dia (por perfil), o robô:
  1. lê os posts recentes das páginas da lista data/radar_perfis.json pela API do Instagram
     (business_discovery: só contas profissionais públicas). Essa leitura só existe no login do
     Facebook: usa o token da Página (FB_PAGE_ID/FB_PAGE_TOKEN) e o Instagram ligado a ela, que só
     lê (serve para os dois perfis);
  2. ordena pelo engajamento (curtidas + 5x comentários: comentário costuma ser "QUERO");
  3. a IA lê a legenda de cada post campeão e traduz o produto em termos de busca genéricos,
     do jeito que o vendedor escreve na Shopee (sem marca, personagem ou celebridade). Quando a
     legenda não diz o produto (carrossel "Digita CASA que mando os links"), uma IA de visão olha
     as fotos dos slides e acha cada produto (um carrossel pode render vários);
  4. guarda os termos em <pasta do perfil>/radar.json. Cada rodada do garimpo gasta alguns
     (config.PALAVRAS_VIRAIS_POR_GARIMPO), antes das buscas da IA e das fixas.

Post já lido não volta. Sem token da Página ou sem IA, o radar só pula (o garimpo segue igual).

Teste: python -m src.radar_virais   (lê as páginas e mostra os termos, sem gravar nada)
"""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import base64
import io

import requests

from . import config, legenda

BRT = timezone(timedelta(hours=-3))
ARQ_PERFIS = config.PASTA_DADOS / "radar_perfis.json"
ARQ_RADAR = config.PASTA_PERFIL / "radar.json"
DIAS_RECENTES = int(os.getenv("RADAR_DIAS", "10"))        # só posts desses últimos dias
POSTS_POR_DIA = int(os.getenv("RADAR_POSTS", "25"))       # campeões que a IA traduz por dia
POSTS_POR_PAGINA = int(os.getenv("RADAR_POSTS_PAGINA", "4"))  # nenhuma página domina o radar
TERMOS_POR_CATEGORIA = 2                                  # por rodada: o radar fica variado
POSTS_COM_FOTO = int(os.getenv("RADAR_POSTS_FOTO", "12"))  # posts por dia que a IA de visão olha
FOTOS_POR_POST = 5                                         # limite da Groq por pedido
MODELOS_VISAO = [m.strip() for m in os.getenv(
    "RADAR_MODELOS_VISAO",
    "meta-llama/llama-4-scout-17b-16e-instruct,meta-llama/llama-4-maverick-17b-128e-instruct").split(",") if m.strip()]
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
        d = None
        for limite in (25, 12, 6):   # página grande com carrossel: a API pede "menos dados" (HTTP 500)
            campo = ("business_discovery.username(%s){username,followers_count,"
                     "media.limit(%d){caption,like_count,comments_count,timestamp,permalink,media_type,"
                     "media_url,thumbnail_url,children{media_type,media_url,thumbnail_url}}}" % (usuario, limite))
            try:
                d = _get(token, ig, campo)["business_discovery"]
                break
            except Exception as e:
                erro = str(e)
                if "reduce the amount" not in erro:
                    break
        if d is None:
            print(f"   📡 @{usuario}: sem dado ({erro[:120]})")
            continue
        midias = (d.get("media") or {}).get("data") or []
        n = 0
        for m in midias:
            quando = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
            if quando < corte or not (m.get("caption") or "").strip():
                continue
            curtidas, coments = int(m.get("like_count") or 0), int(m.get("comments_count") or 0)
            filhos = ((m.get("children") or {}).get("data") or [m])
            imagens = [f.get("thumbnail_url") or f.get("media_url") for f in filhos
                       if f.get("thumbnail_url") or (f.get("media_url") and f.get("media_type") != "VIDEO")]
            saida.append({"perfil": d.get("username", usuario), "permalink": m.get("permalink"),
                          "legenda": m["caption"].strip(), "curtidas": curtidas, "comentarios": coments,
                          "nota": curtidas + PESO_COMENTARIO * coments, "imagens": imagens})
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


PROMPT_FOTOS = """Estas imagens são os slides de um post que BOMBOU numa página de achadinhos do
Instagram (legenda: "{legenda}"). Ajude a página {marca} (público: {publico}).

Identifique cada PRODUTO FÍSICO diferente que aparece (ignore slides só com texto, capa e chamada).
Para cada um, crie 2 ou 3 termos de busca para a Shopee: 2 a 4 palavras, como o VENDEDOR escreve no
título; genéricos, NUNCA marca, personagem, celebridade, time ou franquia.
Categoria: uma de {categorias}, ou "fora" se não combina com o público ou é item de fumo/droga/arma/adulto.

Responda APENAS com JSON: {{"itens": [{{"produto": "...", "categoria": "...", "termos": ["...", "..."]}}]}}"""


def _foto_b64(url):
    """Baixa a imagem e reduz para 640px (menos tokens). None se falhar."""
    try:
        from PIL import Image
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img.thumbnail((640, 640))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _limpar_item(it):
    cat = it.get("categoria")
    termos = [_limpo(t) for t in it.get("termos") or []]
    termos = [t for t in termos if 2 <= len(t.split()) <= 4 and 5 <= len(t) <= 40
              and not any(p in t for p in config.PALAVRAS_PROIBIDAS)]
    return {"produto": it.get("produto", ""), "categoria": cat, "termos": termos} \
        if cat in config.NICHO and termos else None


_visao = {"modelos": None}


def _modelos_visao(headers):
    """Os da config e, se a Groq não tiver nenhum, os modelos de visão que a conta enxerga agora."""
    if _visao["modelos"] is not None:
        return _visao["modelos"]
    try:
        ids = [m["id"] for m in requests.get(f"{config.GROQ_URL}/models", headers=headers, timeout=30).json()["data"]]
    except Exception:
        ids = []
    pistas = ("vision", "llama-4", "scout", "maverick", "-vl", "vl-", "gemma-3", "pixtral", "llava")
    achados = [m for m in ids if any(p in m.lower() for p in pistas)]
    _visao["modelos"] = [m for m in MODELOS_VISAO if m in ids] + [m for m in achados if m not in MODELOS_VISAO]
    print(f"   👁️  modelos de visão na Groq: {_visao['modelos'] or 'nenhum'}")
    return _visao["modelos"]


def ver_fotos(p):
    """Produtos que a IA de visão enxerga nas fotos do post: [{produto, categoria, termos}]."""
    fotos = [b for b in (_foto_b64(u) for u in p.get("imagens", [])[:FOTOS_POR_POST]) if b]
    if not fotos:
        return []
    texto = PROMPT_FOTOS.format(legenda=re.sub(r"\s+", " ", p["legenda"])[:200].replace('"', "'"),
                                marca=config.NOME_MARCA, publico=config.PUBLICO,
                                categorias=", ".join(config.NICHO))
    if (os.getenv("GEMINI_API_KEY") or "").strip():
        return _ver_gemini(texto, fotos)
    if not config.GROQ_API_KEY:
        return []
    conteudo = [{"type": "text", "text": texto}] + [{"type": "image_url", "image_url": {"url": f}} for f in fotos]
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"}
    for modelo in list(_modelos_visao(headers)):
        try:
            r = requests.post(f"{config.GROQ_URL}/chat/completions", headers=headers, timeout=90, json={
                "model": modelo, "temperature": 0.3, "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": conteudo}]})
            if r.status_code == 429:
                time.sleep(min(float(r.headers.get("retry-after", 10) or 10), 30))
                r = requests.post(f"{config.GROQ_URL}/chat/completions", headers=headers, timeout=90, json={
                    "model": modelo, "temperature": 0.3, "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": conteudo}]})
            if r.status_code != 200:
                print(f"   ⚠️  visão {modelo}: HTTP {r.status_code} {r.text[:120]}")
                if r.status_code in (400, 404):
                    _visao["modelos"].remove(modelo)   # não insiste nesse nos próximos posts
                continue
            bruto = r.json()["choices"][0]["message"]["content"]
            itens = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("itens") or []
            return [x for x in (_limpar_item(it) for it in itens if isinstance(it, dict)) if x]
        except Exception as e:
            print(f"   ⚠️  visão {modelo}: {str(e)[:120]}")
    return []


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
_gemini = {"modelos": None}


def _modelos_gemini(chave):
    """O modelo pedido (GEMINI_MODELO), ou os "flash" que a chave enxerga, do mais novo ao mais velho.
    Modelo novo às vezes não tem cota no plano gratuito (HTTP 429), então os outros ficam de reserva."""
    if _gemini["modelos"] is None:
        pedido = os.getenv("GEMINI_MODELO", "").strip()
        nomes = []
        try:
            nomes = [m["name"].split("/")[-1] for m in requests.get(
                f"{GEMINI_URL}/models", params={"key": chave}, timeout=30).json().get("models", [])
                if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        except Exception:
            pass
        ruins = ("exp", "preview", "image", "tts", "live", "audio", "embedding", "thinking")
        flash = sorted((n for n in nomes if "flash" in n and not any(r in n for r in ruins)), reverse=True)
        # o flash normal antes do lite da mesma geração
        flash.sort(key=lambda n: "lite" in n)
        reserva = [n for n in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash") if n not in flash]
        _gemini["modelos"] = ([pedido] if pedido else []) + flash + reserva
    return _gemini["modelos"]


def _ver_gemini(texto, fotos):
    """Visão pelo Gemini (segredo GEMINI_API_KEY, plano gratuito do Google AI Studio)."""
    chave = os.getenv("GEMINI_API_KEY").strip()
    partes = [{"text": texto}] + [{"inline_data": {"mime_type": "image/jpeg", "data": f.split(",", 1)[1]}}
                                   for f in fotos]
    modelos = _modelos_gemini(chave)
    while modelos:
        modelo = modelos[0]
        try:
            r = requests.post(f"{GEMINI_URL}/models/{modelo}:generateContent", params={"key": chave},
                              timeout=90, json={"contents": [{"parts": partes}],
                                                "generationConfig": {"temperature": 0.3,
                                                                     "responseMimeType": "application/json"}})
            espera = re.search(r'"retryDelay": "(\d+)', r.text) if r.status_code == 429 else None
            if espera and "PerMinute" in r.text and int(espera.group(1)) <= 60 and not _gemini.get(modelo):
                _gemini[modelo] = True   # limite por minuto: espera uma vez e tenta de novo
                time.sleep(int(espera.group(1)) + 2)
                continue
            if r.status_code in (400, 403, 404, 429):
                cota = re.findall(r'"quotaId": "([^"]+)"', r.text)[:1]
                print(f"   ⚠️  visão Gemini {modelo}: HTTP {r.status_code} {cota or r.text[:100]} → próximo modelo")
                modelos.pop(0)   # não insiste nesse nos próximos posts
                continue
            if r.status_code != 200:
                print(f"   ⚠️  visão Gemini {modelo}: HTTP {r.status_code} {r.text[:150]}")
                return []
            _gemini.pop(modelo, None)
            if not _gemini.get("avisado"):
                _gemini["avisado"] = True
                print(f"   👁️  visão pelo Gemini: {modelo}")
            bruto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            itens = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("itens") or []
            return [x for x in (_limpar_item(it) for it in itens if isinstance(it, dict)) if x]
        except Exception as e:
            print(f"   ⚠️  visão Gemini {modelo}: {str(e)[:150]}")
            return []
    return []


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
    olhados = 0
    for p, tr in zip(novos, traducoes):
        dados["vistos"][p["permalink"]] = hoje
        achados = [tr] if tr else []
        if not achados and p.get("imagens") and olhados < POSTS_COM_FOTO:
            olhados += 1
            achados = ver_fotos(p)
            if achados:
                print(f"   👁️  fotos de @{p['perfil']} ({len(p['imagens'])} slides): {len(achados)} produtos")
        if not achados:
            print(f"   ⏭️  pulado: {p['legenda'][:70]!r}")
            continue
        for tr in achados:
            print(f"   🔥 {p['curtidas']} curtidas / {p['comentarios']} coments (@{p['perfil']}): "
                  f"{tr['produto']} → {', '.join(tr['termos'])}")
            n += _guardar(dados, ja, tr, p, hoje)
    dados["dia"] = hoje
    return n


def _guardar(dados, ja, tr, p, hoje):
    n = 0
    for termo in tr["termos"]:
        if termo not in ja:
            ja.add(termo)
            dados["termos"].append({"termo": termo, "cat": tr["categoria"], "produto": tr["produto"],
                                    "nota": p["nota"], "perfil": p["perfil"],
                                    "permalink": p["permalink"], "dia": hoje})
            n += 1
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
