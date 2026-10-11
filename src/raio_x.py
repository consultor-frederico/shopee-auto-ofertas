"""📊 Raio-X do Zé — compara um produto com os parecidos da Shopee, só com dados reais.

A Shopee não deixa o robô ler as avaliações dos compradores (a página devolve "acesso negado"),
então o Raio-X usa o que a API de afiliados entrega: nota, vendas e preço. Ele busca os
produtos parecidos e calcula a mediana de preço deles.

- comparar(prod)   → {"termo", "n", "mediana", "pct", "parecidos": [...]}
- linha(oferta)    → "📊 Raio-X do Zé: ⭐ 4,9 · 3.200+ vendidos · 27% abaixo da média de 18 parecidos"
- com_raio_x(leg, oferta) → põe a linha na legenda (antes do "manda/salva" e do "EU QUERO")

Teste: python -m src.raio_x "nome do produto" 59.90
"""
import json
import re
from statistics import median

from . import config

MIN_PARECIDOS = 6          # com menos que isso a média não diz nada
VENDAS_MIN_AMOSTRA = 10    # produto com pouquíssima venda não entra na média
PALAVRAS_VAZIAS = set("""de da do das dos para pra com sem e a o as os em no na kit novo nova original
promocao oferta envio imediato pronta entrega frete gratis unidade unidades pcs pc peças""".split())

PROMPT_TERMO = """Nome de um produto da Shopee: "{nome}"
Responda só com JSON {{"termo": "..."}}: de 1 a 3 palavras, em português, que uma pessoa digitaria
para achar ESSE MESMO TIPO de produto (o substantivo principal e no máximo 1 característica que muda
o produto, ex.: "fone bluetooth", "air fryer", "tapete higiênico"). Sem marca, sem tamanho, sem cor."""


def brl(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _termo_simples(nome):
    from .busca_ze import _norm
    palavras = [p for p in re.findall(r"[a-z0-9]+", _norm(re.sub(r"[\[\(].*?[\]\)]", " ", nome)))
                if p not in PALAVRAS_VAZIAS and not p.isdigit() and len(p) > 2]
    return " ".join(palavras[:2])


def termo(nome):
    """Palavras de busca para achar os parecidos (a IA resume o nome; sem IA, as 2 primeiras palavras)."""
    if config.GROQ_API_KEY:
        try:
            from .legenda import _chamar_groq
            bruto = _chamar_groq(PROMPT_TERMO.format(nome=nome.replace('"', "'")[:200]))
            t = str(json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("termo", "")).strip().lower()
            if 2 < len(t) <= 40:
                return t
        except Exception as e:
            print(f"⚠️  Raio-X: IA não resumiu o nome ({e}).")
    return _termo_simples(nome)


def _buscar(t):
    from . import shopee
    from .garimpar import normalizar
    nos = []
    for pagina, ordem in ((1, 1), (1, 2), (2, 1)):
        try:
            nos += shopee.buscar_ofertas(t, pagina, 50, ordem)
        except Exception as e:
            print(f"⚠️  Raio-X: Shopee '{t}' (pág. {pagina}): {e}")
    vistos, saida = set(), []
    for n in nos:
        o = normalizar(n, "raio_x", t)
        if o["id"] not in vistos and o["preco"] > 0:
            vistos.add(o["id"])
            saida.append(o)
    return saida


def _mesmo_tipo(nome, parecidos):
    """A IA confere quais parecidos são o MESMO tipo de produto (não acessório, não outra coisa)."""
    if not config.GROQ_API_KEY or not parecidos:
        return parecidos
    from .busca_ze import _filtro_ia
    base = sorted(parecidos, key=lambda o: o["vendas"], reverse=True)[:40]
    ok = _filtro_ia(re.sub(r"\s+", " ", nome)[:120], base)
    return parecidos if ok is None else ok


def comparar(prod, t=None, mesmo_tipo=False):
    """prod precisa de "nome" e "preco" (e "id", se houver, para não comparar com ele mesmo).
    mesmo_tipo=True: a IA confere a lista (usado no direct, onde as opções viram sugestão)."""
    from .busca_ze import relevante
    t = t or termo(prod["nome"])
    if not t:
        return {"termo": "", "n": 0, "mediana": None, "pct": None, "parecidos": []}
    todos = [o for o in _buscar(t) if o["id"] != str(prod.get("id", ""))]
    parecidos = [o for o in todos if relevante(o["nome"], t)]
    if len(parecidos) < MIN_PARECIDOS and len(t.split()) > 1:   # termo muito fechado: tenta mais aberto
        t2 = t.split()[0]
        extra = [o for o in _buscar(t2) if o["id"] != str(prod.get("id", "")) and relevante(o["nome"], t2)]
        ids = {o["id"] for o in parecidos}
        parecidos += [o for o in extra if o["id"] not in ids]
    if mesmo_tipo:
        parecidos = _mesmo_tipo(prod["nome"], parecidos)
    amostra = [o["preco"] for o in parecidos if o["vendas"] >= VENDAS_MIN_AMOSTRA]
    if len(amostra) >= MIN_PARECIDOS:
        # tira os extremos (kits enormes, peças avulsas) antes da mediana
        amostra.sort()
        corte = len(amostra) // 10
        amostra = amostra[corte:len(amostra) - corte] if corte else amostra
        med = median(amostra)
        pct = round((prod["preco"] / med - 1) * 100) if med else None
    else:
        med, pct = None, None
    return {"termo": t, "n": len(amostra), "mediana": med, "pct": pct, "parecidos": parecidos}


def _vendas_txt(v):
    if v >= 10000:
        return f"{v // 1000} mil+ vendidos"
    if v >= 1000:
        return f"{v / 1000:.1f}".replace(".", ",").replace(",0", "") + " mil+ vendidos"
    return f"{v}+ vendidos"


def linha(oferta):
    """Linha da legenda. Só fala da média quando o preço está pelo menos 10% abaixo dela."""
    r = oferta.get("raio_x") or {}
    partes = []
    if oferta.get("nota"):
        partes.append(f"⭐ {oferta['nota']:.1f}".replace(".", ","))
    if oferta.get("vendas"):
        partes.append(_vendas_txt(int(oferta["vendas"])))
    if r.get("pct") is not None and r["pct"] <= -10 and r.get("n", 0) >= MIN_PARECIDOS:
        partes.append(f"{-r['pct']}% abaixo da média de {r['n']} parecidos")
    if len(partes) < 2:
        return ""
    return "📊 Raio-X do Zé: " + " · ".join(partes)


def preparar(oferta):
    """Calcula e guarda o Raio-X na oferta (uma vez só). Só Shopee; nunca derruba o post."""
    if oferta.get("raio_x") or oferta.get("plataforma", "shopee") != "shopee" or not oferta.get("nome"):
        return
    try:
        r = comparar(oferta, mesmo_tipo=True)
        oferta["raio_x"] = {"termo": r["termo"], "n": r["n"], "mediana": r["mediana"], "pct": r["pct"]}
        print(f"📊 Raio-X: '{r['termo']}' — {r['n']} parecidos, mediana "
              f"{brl(r['mediana']) if r['mediana'] else '-'}, este {r['pct'] if r['pct'] is not None else '?'}%")
    except Exception as e:
        print(f"⚠️  Raio-X não calculado ({e}).")


def com_raio_x(leg, oferta):
    """Põe (ou atualiza) a linha 📊 antes da linha de compartilhar / do EU QUERO."""
    txt = linha(oferta)
    linhas = [l for l in (leg or "").split("\n") if not l.startswith("📊")]
    if not txt:
        return "\n".join(linhas)
    i = next((k for k, l in enumerate(linhas) if l.startswith(("📲", "🔖")) or "QUERO" in l.upper()), None)
    if i is None:
        corpo, sep, tags = "\n".join(linhas).partition("\n\n#")
        return f"{corpo.rstrip()}\n{txt}" + (f"\n\n#{tags}" if sep else "")
    return "\n".join(linhas[:i] + [txt] + linhas[i:])


if __name__ == "__main__":
    import sys
    nome = sys.argv[1] if len(sys.argv) > 1 else "Fone de Ouvido Bluetooth TWS i12"
    preco = float(sys.argv[2]) if len(sys.argv) > 2 else 29.9
    o = {"nome": nome, "preco": preco, "nota": 4.8, "vendas": 3200, "plataforma": "shopee", "id": "0"}
    preparar(o)
    print(linha(o) or "(sem linha)")
