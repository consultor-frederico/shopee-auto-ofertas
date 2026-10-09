"""Garimpo profundo: escolhe as buscas de cada rodada.

- Termos inventados pela IA a cada rodada (específicos e curiosos, que quase ninguém busca);
- Termos da memória: os que já trouxeram Ouro ou 💎 Achado voltam a ser cavados;
- O resto vem das palavras fixas do nicho (config.NICHO), em rodízio.

A memória fica em config.ARQ_PALAVRAS e vai aprendendo sozinha: termo bom sobe, termo que
não traz nada depois de algumas tentativas é descartado e não é sugerido de novo.
"""
import json
import random
import re
from datetime import datetime, timedelta, timezone

from . import config, legenda

BRT = timezone(timedelta(hours=-3))
USOS_PARA_DESCARTAR = 3      # termo da IA que não trouxe nada em 3 rodadas é descartado
MAX_MEMORIA = 600

PROMPT = """Você é um caçador de achadinhos da Shopee e da AliExpress para a página {marca}
(público: {publico}).
Quero achar produtos DIFERENTES, que quase ninguém posta: gadgets curiosos, soluções espertas
para o dia a dia, itens com efeito visual, "não sabia que precisava disso", presentes criativos.

Crie termos de busca em português do Brasil, como uma pessoa digitaria na busca da Shopee:
- curtos, de 2 a 4 palavras, do jeito que o VENDEDOR escreve no título do anúncio (a busca da
  Shopee é literal: termo comprido demais volta vazio). Ex.: "mini seladora", "luminária lua 3d",
  "porta tempero giratório", "suporte magnético cabo";
- nada genérico ou "de vitrine": NÃO quero "fone bluetooth", "câmera de ação 4k", "suporte celular
  ventosa", "capa de volante", "cama pet", "mochila" — isso todo mundo já posta;
- pense no inusitado e engenhoso, como: "despertador projetor de teto", "lixeira com sensor de
  presença", "escova de dedo para cachorro", "vela de led com sopro", "chaveiro rastreador de item",
  "porta copo térmico para carro", "massageador de couro cabeludo elétrico";
- sem marca, sem preço, sem adjetivos vazios ("barato", "promoção");
- nunca: {proibidas}.

Categorias (com exemplos do estilo de cada uma):
{categorias}

NÃO repita nem varie estes termos já usados: {evitar}

Gere {n} termos NOVOS para cada categoria.
Responda APENAS com JSON: {{"termos": {{"<categoria>": ["...", "..."]}}}}"""


def _hoje():
    return datetime.now(BRT).strftime("%Y-%m-%d")


def _limpo(t):
    return re.sub(r"\s+", " ", str(t or "")).strip().lower()


def carregar():
    mem = {}
    if config.ARQ_PALAVRAS.exists():
        try:
            mem = json.loads(config.ARQ_PALAVRAS.read_text(encoding="utf-8"))
        except ValueError:
            pass
    for chave in ("palavras", "categorias", "lojas"):
        mem.setdefault(chave, {})
    return mem


def salvar(mem):
    if len(mem["lojas"]) > 300:   # guarda só as melhores lojas
        melhores = sorted(mem["lojas"].items(), key=lambda kv: -kv[1].get("achados", 0))[:300]
        mem["lojas"] = dict(melhores)
    pal = mem["palavras"]
    if len(pal) > MAX_MEMORIA:   # esquece primeiro os descartados e os mais antigos
        ordem = sorted(pal, key=lambda k: (not pal[k].get("descartado"), pal[k].get("ultimo_uso", "")))
        for k in ordem[:len(pal) - MAX_MEMORIA]:
            del pal[k]
    config.ARQ_PALAVRAS.parent.mkdir(parents=True, exist_ok=True)
    config.ARQ_PALAVRAS.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")


def termos_da_ia(n_total, mem):
    """{categoria: [termos]} inventados pela IA. Sem IA, devolve {}."""
    if n_total <= 0 or not config.GROQ_API_KEY:
        return {}
    cats = list(config.NICHO)
    por_cat = max(2, -(-n_total // len(cats)) + 1)          # sobra um pouco para filtrar
    exemplos = "\n".join(f"- {c}: {', '.join(random.sample(p, min(4, len(p))))}"
                         for c, p in config.NICHO.items())
    usados = list(mem["palavras"]) + [p for ps in config.NICHO.values() for p in ps]
    evitar = ", ".join(random.sample(usados, min(120, len(usados))))
    prompt = PROMPT.format(marca=config.NOME_MARCA, publico=config.PUBLICO, categorias=exemplos,
                           evitar=evitar, n=por_cat, proibidas=", ".join(config.PALAVRAS_PROIBIDAS))
    try:
        bruto = legenda._chamar_groq(prompt)
        dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
    except Exception as e:
        print(f"⚠️  IA não sugeriu buscas novas ({e}) — seguindo com as palavras fixas.")
        return {}
    ja = set(mem["palavras"]) | {_limpo(p) for ps in config.NICHO.values() for p in ps}
    saida = {}
    for cat, termos in (dados.get("termos") or {}).items():
        if cat not in config.NICHO or not isinstance(termos, list):
            continue
        bons = []
        for t in termos:
            t = _limpo(t)
            if (2 <= len(t.split()) <= 4 and 5 <= len(t) <= 40 and t not in ja
                    and not any(p in t for p in config.PALAVRAS_PROIBIDAS)):
                bons.append(t)
                ja.add(t)
        if bons:
            saida[cat] = bons
    return saida


def termos_da_memoria(n, mem):
    """Os termos que mais trouxeram Ouro/Achado (taxa por uso), sem repetir no mesmo dia."""
    hoje = _hoje()
    bons = [(k, v) for k, v in mem["palavras"].items()
            if v.get("achados", 0) > 0 and not v.get("descartado") and v.get("ultimo_uso") != hoje
            and v.get("cat") in config.NICHO]
    bons.sort(key=lambda kv: kv[1]["achados"] / max(1, kv[1].get("usos", 1)), reverse=True)
    topo = bons[:max(n * 3, n)]
    return [(v["cat"], k) for k, v in random.sample(topo, min(n, len(topo)))]


def escolher_palavras(mem):
    """Lista de (categoria, termo, origem) para a rodada. origem: ia | memoria | fixa."""
    total = config.PALAVRAS_POR_GARIMPO
    escolhidas, vistos = [], set()

    def add(cat, termo, origem):
        t = _limpo(termo)
        if t and t not in vistos and len(escolhidas) < total:
            vistos.add(t)
            escolhidas.append((cat, termo, origem))

    for cat, termo in termos_da_memoria(config.PALAVRAS_MEMORIA_POR_GARIMPO, mem):
        add(cat, termo, "memoria")
    ia = termos_da_ia(config.PALAVRAS_IA_POR_GARIMPO, mem)
    filas = {c: list(t) for c, t in ia.items()}
    n_ia = 0
    while n_ia < config.PALAVRAS_IA_POR_GARIMPO and any(filas.values()):
        for cat in random.sample(list(filas), len(filas)):
            if filas[cat] and n_ia < config.PALAVRAS_IA_POR_GARIMPO:
                add(cat, filas[cat].pop(0), "ia")
                n_ia += 1
    # completa com as palavras fixas, em rodízio entre as categorias
    fixas = {cat: random.sample(p, len(p)) for cat, p in config.NICHO.items()}
    while len(escolhidas) < total and any(fixas.values()):
        for cat in random.sample(list(fixas), len(fixas)):
            if fixas[cat]:
                add(cat, fixas[cat].pop(), "fixa")
    origens = {o: sum(1 for *_, x in escolhidas if x == o) for o in ("ia", "memoria", "fixa")}
    print(f"🧭 Buscas da rodada: {origens['ia']} novas da IA, {origens['memoria']} da memória, "
          f"{origens['fixa']} fixas")
    for cat, termo, origem in escolhidas:
        if origem != "fixa":
            print(f"   {'🧠' if origem == 'memoria' else '✨'} {cat}: {termo}")
    return escolhidas


# --- Categorias da Shopee: o robô aprende sozinho qual categoria da Shopee é de qual nicho nosso ---

def aprender_categorias(mem, nos, categoria):
    """Cada busca por palavra ensina: os produtos de 'fone bluetooth' (eletronicos) têm tais cat_ids."""
    cats = mem["categorias"]
    for no in nos:
        ids = no.get("productCatIds") or []
        for nivel, c in enumerate(ids):
            if not c:
                continue
            reg = cats.setdefault(str(c), {"nivel": nivel, "votos": {}})
            reg["votos"][categoria] = reg["votos"].get(categoria, 0) + 1


def _dono(reg, minimo=5, fatia=0.7):
    votos = reg.get("votos") or {}
    total = sum(votos.values())
    if total < minimo:
        return None
    cat, n = max(votos.items(), key=lambda kv: kv[1])
    return cat if n / total >= fatia and cat in config.NICHO else None


def categoria_de(mem, cat_ids):
    """Nosso nicho para um produto, pela categoria mais específica que o robô já conhece."""
    for c in reversed(cat_ids or []):
        reg = mem["categorias"].get(str(c))
        if reg:
            dono = _dono(reg)
            if dono:
                return dono
    return None


def categorias_para_garimpar(mem, n):
    """Categorias específicas (nível 2+) com dono claro; as que já renderam achados têm prioridade."""
    hoje = _hoje()
    opcoes = [(c, reg) for c, reg in mem["categorias"].items()
              if c != "0" and reg.get("nivel", 0) >= 2 and _dono(reg, minimo=15, fatia=0.75)
              and reg.get("ultimo_uso") != hoje]
    if not opcoes:
        return []
    peso = [1 + 3 * reg.get("achados", 0) for _, reg in opcoes]
    escolha, vistos = [], set()
    while len(escolha) < n and len(vistos) < len(opcoes):
        c, reg = random.choices(opcoes, weights=peso)[0]
        if c not in vistos:
            vistos.add(c)
            escolha.append((c, _dono(reg, minimo=15, fatia=0.75)))
    return escolha


# --- Lojas garimpeiras: loja que já deu Ouro/Achado costuma ter outros produtos diferentes ---

def lojas_para_garimpar(mem, n):
    hoje = _hoje()
    lojas = [(k, v) for k, v in mem["lojas"].items() if v.get("ultimo_uso") != hoje]
    lojas.sort(key=lambda kv: kv[1].get("achados", 0) / max(1, kv[1].get("usos", 0) + 1), reverse=True)
    topo = lojas[:max(n * 3, n)]
    return [(k, v.get("nome", "")) for k, v in random.sample(topo, min(n, len(topo)))]


def marcar_uso(mem, tipo, chave):
    reg = mem[tipo].setdefault(str(chave), {})
    reg["usos"] = reg.get("usos", 0) + 1
    reg["ultimo_uso"] = _hoje()


def registrar(mem, escolhidas, aprovados):
    """Atualiza a memória com o resultado da rodada."""
    hoje = _hoje()
    ganhos = {}
    for o in aprovados:
        if o.get("nivel") not in ("ouro", "achado"):
            continue
        ganhos[_limpo(o["palavra"])] = ganhos.get(_limpo(o["palavra"]), 0) + 1
        if o.get("loja_id"):
            reg = mem["lojas"].setdefault(str(o["loja_id"]), {"nome": o.get("loja", ""), "achados": 0,
                                                               "usos": 0, "desde": hoje})
            reg["achados"] = reg.get("achados", 0) + 1
        for c in (o.get("cat_ids") or [])[2:]:
            if str(c) in mem["categorias"]:
                mem["categorias"][str(c)]["achados"] = mem["categorias"][str(c)].get("achados", 0) + 1
    for cat, termo, origem in escolhidas:
        k = _limpo(termo)
        reg = mem["palavras"].setdefault(k, {"cat": cat, "origem": origem, "usos": 0, "achados": 0,
                                             "criado": hoje})
        reg["usos"] += 1
        reg["achados"] += ganhos.get(k, 0)
        reg["ultimo_uso"] = hoje
        if reg.get("origem") == "ia" and reg["achados"] == 0 and reg["usos"] >= USOS_PARA_DESCARTAR:
            reg["descartado"] = True
    bons = sorted(((k, v) for k, v in ganhos.items()), key=lambda kv: -kv[1])[:5]
    if bons:
        print("🏆 Buscas que mais renderam nesta rodada: " + ", ".join(f"{k} ({v})" for k, v in bons))
