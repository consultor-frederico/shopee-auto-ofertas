"""Etapa 1 — Garimpo: busca ofertas no nicho, filtra, gera a legenda e põe na fila.

Uso: python -m src.garimpar
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone

from . import config, legenda, shopee

BRT = timezone(timedelta(hours=-3))
FMT = "%Y-%m-%d %H:%M:%S"


def agora():
    return datetime.now(BRT)


def carregar_fila():
    if config.ARQ_FILA.exists():
        return json.loads(config.ARQ_FILA.read_text(encoding="utf-8"))
    return {"ofertas": {}}


def salvar_fila(fila):
    config.PASTA_DADOS.mkdir(exist_ok=True)
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


def motivo_recusa(o):
    nome = o["nome"].lower()
    if not o["link_afiliado"] or not o["imagem"]:
        return "sem link ou imagem"
    if o["nota"] < config.NOTA_MINIMA:
        return "nota baixa"
    if o["vendas"] < config.VENDAS_MINIMAS:
        return "poucas vendas"
    if o["comissao"] < config.COMISSAO_MINIMA_RS:
        return "comissão baixa"
    if o["preco"] <= 0 or o["preco"] > config.PRECO_MAXIMO:
        return "preço fora da faixa"
    if any(p in nome for p in config.PALAVRAS_PROIBIDAS):
        return "palavra proibida"
    return None


def pontuar(o):
    """Prioriza o que converte (nota e vendas) e o que paga (comissão)."""
    return round(o["comissao"] * 2 + min(o["vendas"], 20000) / 1000
                 + (o["nota"] - 4.5) * 10 + o["desconto"] / 10, 2)


def ja_usado(fila, item_id):
    reg = fila["ofertas"].get(item_id)
    if not reg:
        return False
    return agora() - datetime.strptime(reg["criado_em"], FMT).replace(tzinfo=BRT) \
        <= timedelta(days=config.DIAS_SEM_REPETIR)


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
    pares = [(cat, p) for cat, palavras in config.NICHO.items() for p in palavras]
    random.shuffle(pares)
    # garante as três categorias em cada garimpo
    escolhidas, vistas = [], set()
    for cat, p in pares:
        if cat not in vistas:
            escolhidas.append((cat, p))
            vistas.add(cat)
    escolhidas += [x for x in pares if x not in escolhidas][: max(0, config.PALAVRAS_POR_GARIMPO - len(escolhidas))]

    candidatos, recusas, erros = {}, {}, 0
    for cat, palavra in escolhidas:
        try:
            nos = buscar(palavra)
        except Exception as e:
            erros += 1
            print(f"❌ Busca '{palavra}': {e}")
            continue
        print(f"🔎 '{palavra}' ({cat}): {len(nos)} resultados")
        for no in nos:
            o = normalizar(no, cat, palavra)
            if o["id"] in candidatos or ja_usado(fila, o["id"]):
                continue
            m = motivo_recusa(o)
            if m:
                recusas[m] = recusas.get(m, 0) + 1
                continue
            o["pontos"] = pontuar(o)
            candidatos[o["id"]] = o
    print(f"📊 Aprovados: {len(candidatos)} | Recusados: {recusas}")
    if erros == len(escolhidas):
        raise RuntimeError("Todas as buscas na Shopee falharam — verifique os segredos e a API.")
    return list(candidatos.values())


def selecionar(candidatos, n):
    """Pega os melhores, equilibrando as categorias."""
    por_cat = {}
    for o in sorted(candidatos, key=lambda x: x["pontos"], reverse=True):
        por_cat.setdefault(o["categoria"], []).append(o)
    escolhidos, palavras = [], set()
    # 1ª passada: no máximo 1 oferta por palavra-chave (evita 3 produtos iguais)
    for unico in (True, False):
        restos = {c: list(v) for c, v in por_cat.items()}
        while len(escolhidos) < n and any(restos.values()):
            for cat in list(restos):
                while restos[cat] and len(escolhidos) < n:
                    o = restos[cat].pop(0)
                    if o in escolhidos or (unico and o["palavra"] in palavras):
                        continue
                    escolhidos.append(o)
                    palavras.add(o["palavra"])
                    break
    return escolhidos


def garimpar(buscar=shopee.buscar_ofertas):
    fila = carregar_fila()
    limpar_fila(fila)
    candidatos = coletar_candidatos(fila, buscar)
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
        print(f"✅ {o['categoria']:<11} R$ {o['preco_fmt']:>8}  comissão R$ {o['comissao']:.2f}  {o['titulo']}")
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
