"""Etapa 1 — Garimpo: busca ofertas no nicho, filtra, gera a legenda e põe na fila.

Uso: python -m src.garimpar
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone

from . import aliexpress, config, curadoria, legenda, shopee

BRT = timezone(timedelta(hours=-3))
FMT = "%Y-%m-%d %H:%M:%S"


def agora():
    return datetime.now(BRT)


def carregar_fila():
    if config.ARQ_FILA.exists():
        return json.loads(config.ARQ_FILA.read_text(encoding="utf-8"))
    return {"ofertas": {}}


def salvar_fila(fila):
    config.ARQ_FILA.parent.mkdir(parents=True, exist_ok=True)
    config.ARQ_FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")


def _num(v, padrao=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return padrao


def normalizar(no, categoria, palavra):
    preco = _num(no.get("priceMin"))
    desconto = int(_num(no.get("priceDiscountRate")))
    if 0 < desconto < 1:          # caso a API devolva fração (0.3) em vez de inteiro (30)
        desconto = int(desconto * 100)
    preco_de = round(preco / (1 - desconto / 100), 2) if 5 <= desconto < 90 else None
    return {
        "id": str(no["itemId"]),
        "nome": (no.get("productName") or "").strip(),
        "categoria": categoria,
        "palavra": palavra,
        "preco": preco,
        "preco_fmt": f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "preco_de": preco_de,
        "desconto": desconto if preco_de else 0,
        "comissao": round(_num(no.get("commission")), 2),
        "comissao_pct": round(_num(no.get("commissionRate")) * 100, 1),
        "vendas": int(_num(no.get("sales"))),
        "nota": round(_num(no.get("ratingStar")), 1),
        "loja": no.get("shopName") or "",
        "plataforma": "shopee",
        "imagem": no.get("imageUrl") or "",
        "link_afiliado": no.get("offerLink") or "",
    }


def _pct_min(o, nivel_cfg):
    """A AliExpress paga 7% padrão no Brasil: lá o mínimo em % é o da config.COMISSAO_PCT_ALIEXPRESS
    (o mínimo em R$ continua igual, então só passa produto que paga bem de verdade)."""
    if o.get("plataforma") == "aliexpress":
        return min(nivel_cfg["comissao_pct"], config.COMISSAO_PCT_ALIEXPRESS)
    return nivel_cfg["comissao_pct"]


def motivo_recusa(o):
    """Corte duro do nível Prata (o mínimo para entrar na fila)."""
    prata = config.NIVEIS["prata"]
    nome = o["nome"].lower()
    if not o["link_afiliado"] or not o["imagem"]:
        return "sem link ou imagem"
    if o["nota"] < config.NOTA_MINIMA:
        return "nota baixa"
    if o["vendas"] < prata["vendas"]:
        return "poucas vendas"
    if o["comissao"] < prata["comissao_rs"] or o["comissao_pct"] < _pct_min(o, prata):
        return "comissão baixa"
    if o["preco"] <= 0 or o["preco"] > config.PRECO_MAXIMO:
        return "preço fora da faixa"
    if any(p in nome for p in config.PALAVRAS_PROIBIDAS):
        return "palavra proibida"
    return None


def nivel(o):
    """'ouro', 'prata' ou None, combinando números e fator uau."""
    for nome in ("ouro", "prata"):
        n = config.NIVEIS[nome]
        if (o["vendas"] >= n["vendas"] and o["comissao"] >= n["comissao_rs"]
                and o["comissao_pct"] >= _pct_min(o, n) and o.get("uau", 0) >= n["uau"]):
            return nome
    return None


def pontuar(o):
    """Prioriza o que é diferente (uau), o que paga (comissão) e o que converte (vendas, nota)."""
    return round(o.get("uau", 5) * 3 + min(o["comissao"], 60) * 1.2 + min(o["vendas"], 20000) / 800
                 + (o["nota"] - 4.5) * 10 + o["desconto"] / 10, 2)


def _dias(reg):
    return (agora() - datetime.strptime(reg["criado_em"], FMT).replace(tzinfo=BRT)).days


def ja_usado(fila, item_id):
    """True = bloqueado. Entre 14 e 30 dias, o produto pode voltar só para o Telegram."""
    reg = fila["ofertas"].get(item_id)
    if not reg:
        return False
    return _dias(reg) < config.DIAS_SEM_REPETIR_TELEGRAM


def so_telegram(fila, item_id):
    reg = fila["ofertas"].get(item_id)
    return bool(reg) and _dias(reg) < config.DIAS_SEM_REPETIR


def limpar_fila(fila):
    """Vence pendentes antigos e esquece registros além do prazo de não repetição."""
    limite_pend = agora() - timedelta(days=config.DIAS_VALIDADE_PENDENTE)
    limite_hist = agora() - timedelta(days=config.DIAS_SEM_REPETIR + 5)
    for item_id, reg in list(fila["ofertas"].items()):
        criado = datetime.strptime(reg["criado_em"], FMT).replace(tzinfo=BRT)
        if criado < limite_hist:
            del fila["ofertas"][item_id]
        elif reg["status"] == "pendente" and criado < limite_pend:
            reg["status"] = "vencido"


def coletar_candidatos(fila, buscar=shopee.buscar_ofertas):
    # mesma quantidade de palavras-chave por categoria (rodízio), sorteadas a cada garimpo
    filas = {cat: random.sample(palavras, len(palavras)) for cat, palavras in config.NICHO.items()}
    escolhidas = []
    while len(escolhidas) < config.PALAVRAS_POR_GARIMPO and any(filas.values()):
        for cat in random.sample(list(filas), len(filas)):
            if filas[cat] and len(escolhidas) < config.PALAVRAS_POR_GARIMPO:
                escolhidas.append((cat, filas[cat].pop()))

    candidatos, recusas, erros = {}, {}, 0
    for cat, palavra in escolhidas:
        nos, falhou = [], 0
        for pagina, ordem in ((1, 2), (2, 2), (1, 5)):   # 2 páginas dos mais vendidos + maior comissão
            try:
                nos += buscar(palavra, pagina=pagina, ordem=ordem)
            except TypeError:
                nos += buscar(palavra)
                break
            except Exception as e:
                falhou += 1
                print(f"❌ Busca '{palavra}' (pág. {pagina}, ordem {ordem}): {e}")
        if falhou == 3:
            erros += 1
            continue
        print(f"🔎 '{palavra}' ({cat}): {len(nos)} resultados")
        ofertas = [normalizar(no, cat, palavra) for no in nos]
        if aliexpress.configurado():
            try:
                ae = aliexpress.buscar_produtos(palavra)
                print(f"   🅰️ AliExpress: {len(ae)} resultados com entrega rápida")
                ofertas += [aliexpress.normalizar(p, cat, palavra) for p in ae]
            except Exception as e:
                print(f"⚠️  AliExpress '{palavra}': {e}")
        for o in ofertas:
            if o["id"] in candidatos or ja_usado(fila, o["id"]):
                continue
            m = motivo_recusa(o) or (aliexpress.recusa_extra(o) if o["plataforma"] == "aliexpress" else None)
            if m:
                recusas[m] = recusas.get(m, 0) + 1
                continue
            o["so_telegram"] = so_telegram(fila, o["id"])
            candidatos[o["id"]] = o
    print(f"📊 Passaram nos números: {len(candidatos)} | Recusados: {recusas}")
    if erros == len(escolhidas):
        raise RuntimeError("Todas as buscas na Shopee falharam — verifique os segredos e a API.")
    return list(candidatos.values())


def selecionar(candidatos, n):
    """Pega os melhores, equilibrando as categorias."""
    por_cat = {}
    for o in sorted(candidatos, key=lambda x: x["pontos"], reverse=True):
        por_cat.setdefault(o["categoria"], []).append(o)
    escolhidos, palavras, tipos = [], set(), {}
    # 1ª passada: no máximo 1 oferta por palavra-chave e 2 do mesmo tipo (ex.: "espelho");
    # 2ª passada completa o que faltar, ainda com no máximo 3 do mesmo tipo.
    for unico, max_tipo in ((True, 2), (False, 3)):
        restos = {c: list(v) for c, v in por_cat.items()}
        while len(escolhidos) < n and any(restos.values()):
            for cat in list(restos):
                while restos[cat] and len(escolhidos) < n:
                    o = restos[cat].pop(0)
                    t = tipo_produto(o["nome"])
                    if o in escolhidos or (unico and o["palavra"] in palavras) or tipos.get(t, 0) >= max_tipo:
                        continue
                    escolhidos.append(o)
                    palavras.add(o["palavra"])
                    tipos[t] = tipos.get(t, 0) + 1
                    break
    return escolhidos


_GENERICAS = {"mini", "super", "premium", "conjunto", "jogo", "par", "oferta", "moderno", "moderna", "pares", "peças", "pecas"}


def tipo_produto(nome):
    """Primeira palavra significativa do nome ("Espelho Oval LED" → "espelho")."""
    for p in curadoria._norm(nome):   # palavras em ordem, sem acento
        if p not in _GENERICAS and p not in curadoria.PARADAS and not p.isdigit():
            return p
    return nome.lower()[:10]


def curar(fila, candidatos, max_ia=80):
    """Remove repetidos/parecidos, pede a nota de uau à IA e classifica em ouro/prata."""
    recentes = [r.get("nome", "") for r in fila["ofertas"].values()
                if r.get("nome") and r.get("status") in ("pendente", "postado")]
    mesmas = {(r.get("loja"), r.get("preco")) for r in fila["ofertas"].values()
              if r.get("loja") and r.get("status") in ("pendente", "postado")}
    unicos = []
    for o in sorted(candidatos, key=lambda x: (x["comissao"], x["vendas"]), reverse=True):
        chave = (o.get("loja"), o.get("preco"))
        if (o.get("loja") and chave in mesmas) or \
                any(curadoria.parecido(o["nome"], n, config.SIMILARIDADE_MAX) for n in recentes):
            continue
        unicos.append(o)
        recentes.append(o["nome"])
        mesmas.add(chave)
    print(f"🔁 Sem repetidos/parecidos: {len(unicos)} de {len(candidatos)}")
    unicos = unicos[:max_ia]
    notas = curadoria.notas_uau(unicos)
    if not notas:
        print(f"::warning::Curadoria por IA indisponível — usando nota de uau padrão {config.UAU_SEM_IA}.")
    aprovados, cont = [], {"ouro": 0, "prata": 0, "descartado": 0}
    for o in unicos:
        o["uau"] = notas.get(o["id"], config.UAU_SEM_IA)
        o["nivel"] = nivel(o)
        if not o["nivel"]:
            cont["descartado"] += 1
            continue
        cont[o["nivel"]] += 1
        o["pontos"] = pontuar(o) + (15 if o["nivel"] == "ouro" else 0)
        aprovados.append(o)
    print(f"🏅 Ouro: {cont['ouro']} | 🥈 Prata: {cont['prata']} | descartados pela curadoria: {cont['descartado']}")
    return aprovados


def garimpar(buscar=shopee.buscar_ofertas):
    fila = carregar_fila()
    limpar_fila(fila)
    candidatos = curar(fila, coletar_candidatos(fila, buscar))
    escolhidos = selecionar(candidatos, config.OFERTAS_POR_GARIMPO)
    fontes_ia = 0
    for o in escolhidos:
        texto = legenda.gerar(o)
        o["titulo"], o["legenda"] = texto["titulo"], texto["legenda"]
        fontes_ia += texto["fonte"] == "ia"
        # a arte/Reels é gerada só na hora de postar (não ocupa espaço no repositório)
        o.update({"status": "pendente",
                  "criado_em": agora().strftime(FMT), "postado_em": "", "id_post": ""})
        fila["ofertas"][o["id"]] = o
        selo = "🏅" if o["nivel"] == "ouro" else "🥈"
        print(f"{selo} {o['categoria']:<11} R$ {o['preco_fmt']:>8}  comissão R$ {o['comissao']:.2f} "
              f"({o['comissao_pct']:.0f}%)  {o['vendas']} vendas  uau {o['uau']:.0f}  {o['titulo']}")
    fila["ultimo_garimpo"] = agora().strftime(FMT)
    salvar_fila(fila)
    pend = sum(1 for r in fila["ofertas"].values() if r["status"] == "pendente")
    print(f"\n🏁 {len(escolhidos)} novas ofertas ({fontes_ia} com legenda da IA). Pendentes na fila: {pend}.")
    if escolhidos and fontes_ia == 0 and config.GROQ_API_KEY:
        print("::warning::Nenhuma legenda saiu da IA — veja os avisos da Groq acima.")
    return escolhidos


if __name__ == "__main__":
    try:
        garimpar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
