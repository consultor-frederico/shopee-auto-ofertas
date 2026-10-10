"""Etapa 1 — Garimpo: busca ofertas no nicho, filtra, gera a legenda e põe na fila.

Uso: python -m src.garimpar
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone

from . import aliexpress, busca_profunda, config, curadoria, legenda, shopee

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
    from .precos import ajustar_de
    return ajustar_de({
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
        "loja_id": no.get("shopId"),
        "cat_ids": no.get("productCatIds") or [],
        "plataforma": "shopee",
        "imagem": no.get("imageUrl") or "",
        "link_afiliado": no.get("offerLink") or "",
        "preco_max": _num(no.get("priceMax")) or None,
    })


def _pct_min(o, nivel_cfg):
    """A AliExpress paga 7% padrão no Brasil: lá o mínimo em % é o da config.COMISSAO_PCT_ALIEXPRESS
    (o mínimo em R$ continua igual, então só passa produto que paga bem de verdade)."""
    if o.get("plataforma") == "aliexpress":
        return min(nivel_cfg["comissao_pct"], config.COMISSAO_PCT_ALIEXPRESS)
    return nivel_cfg["comissao_pct"]


def candidato_achado(o):
    """Poucas vendas (abaixo do Prata) e nota alta: pode virar 💎 Achado escondido se o uau for alto."""
    a = config.NIVEL_ACHADO
    return a["vendas_min"] <= o["vendas"] < config.NIVEIS["prata"]["vendas"] and o["nota"] >= a["nota"]


def motivo_recusa(o):
    """Corte duro: o mínimo para entrar na fila (Prata, ou possível 💎 Achado com regras próprias)."""
    prata = config.NIVEIS["prata"]
    nome = o["nome"].lower()
    if not o["link_afiliado"] or not o["imagem"]:
        return "sem link ou imagem"
    if o["nota"] < config.NOTA_MINIMA:
        return "nota baixa"
    achado = candidato_achado(o)
    if o["vendas"] < prata["vendas"] and not achado:
        return "poucas vendas"
    minimo = config.NIVEL_ACHADO if achado else prata   # achado: comissão a partir de R$ 3
    if o["comissao"] < minimo["comissao_rs"] or o["comissao_pct"] < _pct_min(o, minimo):
        return "comissão baixa"
    if o["preco"] <= 0 or o["preco"] > config.PRECO_MAXIMO:
        return "preço fora da faixa"
    if any(p in nome for p in config.PALAVRAS_PROIBIDAS):
        return "palavra proibida"
    return None


def nivel(o):
    """'ouro', 'prata', 'achado' (💎 escondido) ou None, combinando números e fator uau."""
    for nome in ("ouro", "prata"):
        n = config.NIVEIS[nome]
        if (o["vendas"] >= n["vendas"] and o["comissao"] >= n["comissao_rs"]
                and o["comissao_pct"] >= _pct_min(o, n) and o.get("uau", 0) >= n["uau"]):
            return nome
    a = config.NIVEL_ACHADO
    if (candidato_achado(o) and o.get("uau", 0) >= a["uau"]
            and o["comissao"] >= a["comissao_rs"] and o["comissao_pct"] >= _pct_min(o, a)):
        return "achado"
    return None


BONUS_NIVEL = {"ouro": 15, "achado": 18, "prata": 0}
SELO = {"ouro": "🏅", "achado": "💎", "prata": "🥈"}


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


def _buscar_paginas(buscar, alvo, paginas):
    """Busca várias páginas/ordens; para de descer quando a página vem incompleta.
    Cada item de 'paginas' é (página, ordem) ou (página, ordem, "ams")."""
    nos, falhou, esgotou = [], 0, set()
    for pagina, ordem, *extra in paginas:
        ams = "ams" in extra
        chave = (ordem, ams)
        if chave in esgotou:
            continue
        try:
            r = buscar(alvo, pagina=pagina, ordem=ordem, ams=True) if ams else buscar(alvo, pagina=pagina, ordem=ordem)
        except TypeError:
            if ams:
                continue
            return buscar(alvo), False
        except Exception as e:
            falhou += 1
            print(f"❌ Busca '{alvo}' (pág. {pagina}, ordem {ordem}{', ams' if ams else ''}): {e}")
            continue
        nos += r
        if len(r) < 50:
            esgotou.add(chave)
    return nos, falhou == len(paginas)


def _filtrar(fila, ofertas, origem, candidatos, recusas):
    for o in ofertas:
        if o["id"] in candidatos or ja_usado(fila, o["id"]):
            continue
        m = motivo_recusa(o) or (aliexpress.recusa_extra(o) if o["plataforma"] == "aliexpress" else None)
        if m:
            recusas[m] = recusas.get(m, 0) + 1
            continue
        o["so_telegram"] = so_telegram(fila, o["id"])
        o["origem_busca"] = origem
        candidatos[o["id"]] = o


def _por_categoria_aprendida(mem, nos, rotulo):
    """Produtos de loja/categoria não têm palavra: o nicho vem das categorias que o robô aprendeu."""
    ofertas = []
    for no in nos:
        cat = busca_profunda.categoria_de(mem, no.get("productCatIds"))
        if cat:
            ofertas.append(normalizar(no, cat, rotulo))
    return ofertas


TERMOS_LOJA = ["utilidades", "variedades", "importados", "store", "shop", "casa", "pet", "tech",
               "eletronicos", "auto", "brinquedos", "kids", "achados", "presentes", "gadgets", "magazine"]


def coletar_extras(fila, mem, candidatos, recusas):
    """Garimpo além das palavras: lojas que já deram achado, lojas de comissão alta e categorias."""
    lojas = busca_profunda.lojas_para_garimpar(mem, config.LOJAS_POR_GARIMPO)
    # completa com lojas de comissão alta da Shopee (a busca de lojas procura no NOME da loja)
    for termo in random.sample(TERMOS_LOJA, 3):
        if len(lojas) >= config.LOJAS_POR_GARIMPO:
            break
        try:
            achadas = shopee.buscar_lojas(termo, limite=20)
        except Exception as e:
            print(f"⚠️  Lojas de comissão alta ('{termo}'): {e}")
            continue
        boas = [l for l in achadas if float(l.get("commissionRate") or 0) >= 0.15
                and float(l.get("ratingStar") or 0) >= 4.7 and str(l["shopId"]) not in dict(lojas)]
        print(f"🔍 Lojas '{termo}': {len(achadas)} encontradas, {len(boas)} com comissão ≥ 15% e nota ≥ 4,7")
        for l in random.sample(boas, len(boas)):
            if len(lojas) >= config.LOJAS_POR_GARIMPO:
                break
            lojas.append((str(l["shopId"]), l.get("shopName", "")))
    for shop_id, nome in lojas:
        nos = []
        for pagina in (1, 2):
            try:
                r = shopee.buscar_loja(shop_id, pagina=pagina)
            except Exception as e:
                print(f"❌ Loja {nome or shop_id}: {e}")
                break
            nos += r
            if len(r) < 50:
                break
        busca_profunda.marcar_uso(mem, "lojas", shop_id)
        mem["lojas"][str(shop_id)].setdefault("nome", nome)
        ofertas = _por_categoria_aprendida(mem, nos, f"loja {nome or shop_id}")
        print(f"🏪 Loja '{nome or shop_id}': {len(nos)} produtos ({len(ofertas)} do nosso nicho)")
        _filtrar(fila, ofertas, "loja", candidatos, recusas)
    for cat_id, nicho in busca_profunda.categorias_para_garimpar(mem, config.CATEGORIAS_POR_GARIMPO):
        nos, _ = _buscar_paginas(lambda alvo, **kw: shopee.buscar_categoria(alvo, **kw), cat_id,
                                 config.PAGINAS_CATEGORIA)
        busca_profunda.marcar_uso(mem, "categorias", cat_id)
        ofertas = [normalizar(no, nicho, f"categoria {cat_id}") for no in nos]
        print(f"🗂️  Categoria {cat_id} ({nicho}): {len(nos)} produtos")
        _filtrar(fila, ofertas, "categoria", candidatos, recusas)


def coletar_candidatos(fila, buscar=shopee.buscar_ofertas, escolhidas=None, mem=None):
    mem = mem if mem is not None else busca_profunda.carregar()
    if escolhidas is None:
        escolhidas = busca_profunda.escolher_palavras(mem)
    candidatos, recusas, erros = {}, {}, 0
    for cat, palavra, origem in escolhidas:
        profunda = origem != "fixa"
        nos, falhou_tudo = _buscar_paginas(
            buscar, palavra, config.PAGINAS_PROFUNDAS if profunda else config.PAGINAS_FIXAS)
        if falhou_tudo:
            erros += 1
            continue
        print(f"🔎 '{palavra}' ({cat}{', ' + origem if profunda else ''}): {len(nos)} resultados")
        busca_profunda.aprender_categorias(mem, nos, cat)
        ofertas = [normalizar(no, cat, palavra) for no in nos]
        if aliexpress.configurado():
            ae = []
            buscas_ae = [("busca", 1)] + ([("alta", 1), ("busca", 2)] if profunda else [])
            for tipo, pag in buscas_ae:
                try:
                    metodo = aliexpress.METODO_EM_ALTA if tipo == "alta" else aliexpress.METODO_BUSCA
                    ae += aliexpress.buscar_produtos(palavra, pagina=pag, metodo=metodo)
                except Exception as e:
                    if "result is empty" not in str(e).lower():   # busca sem resultado não é erro
                        print(f"⚠️  AliExpress '{palavra}' ({tipo}, pág. {pag}): {e}")
            if ae:
                print(f"   🅰️ AliExpress: {len(ae)} resultados com entrega rápida")
            ofertas += [aliexpress.normalizar(p, cat, palavra) for p in ae]
        _filtrar(fila, ofertas, origem, candidatos, recusas)
    if escolhidas and erros == len(escolhidas):
        raise RuntimeError("Todas as buscas na Shopee falharam — verifique os segredos e a API.")
    if buscar is shopee.buscar_ofertas:   # (nos testes com busca simulada, pula as lojas/categorias)
        try:
            coletar_extras(fila, mem, candidatos, recusas)
        except Exception as e:
            print(f"⚠️  Garimpo em lojas/categorias falhou ({e}) — seguindo com as palavras.")
    por_origem = {}
    for o in candidatos.values():
        por_origem[o["origem_busca"]] = por_origem.get(o["origem_busca"], 0) + 1
    print(f"📊 Passaram nos números: {len(candidatos)} {por_origem} | Recusados: {recusas}")
    return list(candidatos.values())


def selecionar(candidatos, n, ja_na_fila=None):
    """Pega os melhores, equilibrando as categorias e sem lotar a fila do mesmo tipo de produto."""
    from . import variedade
    fams = dict(ja_na_fila or {})
    por_cat = {}
    for o in sorted(candidatos, key=lambda x: x["pontos"], reverse=True):
        por_cat.setdefault(o["categoria"], []).append(o)
    escolhidos, palavras, tipos, por_palavra = [], set(), {}, {}
    # 1ª passada: no máximo 1 oferta por palavra-chave e 1 de cada tipo (ex.: "smartwatch");
    # 2ª passada completa o que faltar, ainda com no máximo 2 do mesmo tipo.
    for unico, max_tipo in ((True, 1), (False, 2)):
        restos = {c: list(v) for c, v in por_cat.items()}
        while len(escolhidos) < n and any(restos.values()):
            for cat in list(restos):
                while restos[cat] and len(escolhidos) < n:
                    o = restos[cat].pop(0)
                    t = tipo_produto(o["nome"])
                    f = variedade.familia(o)
                    if (o in escolhidos or (unico and o["palavra"] in palavras) or tipos.get(t, 0) >= max_tipo
                            or por_palavra.get(o["palavra"], 0) >= 2
                            or fams.get(f, 0) >= config.MAX_PENDENTES_POR_FAMILIA):
                        continue
                    fams[f] = fams.get(f, 0) + 1
                    escolhidos.append(o)
                    palavras.add(o["palavra"])
                    por_palavra[o["palavra"]] = por_palavra.get(o["palavra"], 0) + 1
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


def curar(fila, candidatos, max_ia=120, max_achado=30):
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
    # vaga reservada para possíveis 💎 achados (poucas vendas ficariam no fim da fila da IA)
    poucos = sorted((o for o in unicos if o["vendas"] < config.NIVEIS["prata"]["vendas"]),
                    key=lambda x: (x["nota"], x["comissao"]), reverse=True)[:max_achado]
    normais = [o for o in unicos if o["vendas"] >= config.NIVEIS["prata"]["vendas"]]
    unicos = normais[:max_ia - len(poucos)] + poucos
    notas = curadoria.notas_uau(unicos)
    if not notas:
        print(f"::warning::Curadoria por IA indisponível — usando nota de uau padrão {config.UAU_SEM_IA}.")
    aprovados, cont = [], {"ouro": 0, "achado": 0, "prata": 0, "descartado": 0}
    for o in unicos:
        o["uau"] = notas.get(o["id"], config.UAU_SEM_IA)
        o["nivel"] = nivel(o)
        if not o["nivel"]:
            cont["descartado"] += 1
            continue
        cont[o["nivel"]] += 1
        # bônus para o que veio da busca profunda (termos da IA/memória): é o que dá cara de garimpo
        o["pontos"] = pontuar(o) + BONUS_NIVEL[o["nivel"]] + (8 if o.get("origem_busca") in ("ia", "memoria", "loja", "categoria") else 0)
        aprovados.append(o)
    orig = {}
    for o in aprovados:
        if o["nivel"] in ("ouro", "achado"):
            orig[o.get("origem_busca", "?")] = orig.get(o.get("origem_busca", "?"), 0) + 1
    print(f"🧭 Ouro/Achado por origem da busca: {orig}")
    print(f"🏅 Ouro: {cont['ouro']} | 💎 Achado escondido: {cont['achado']} | 🥈 Prata: {cont['prata']} | "
          f"descartados pela curadoria: {cont['descartado']}")
    return aprovados


def garimpar(buscar=shopee.buscar_ofertas):
    fila = carregar_fila()
    limpar_fila(fila)
    memoria = busca_profunda.carregar()
    escolhidas = busca_profunda.escolher_palavras(memoria)
    candidatos = curar(fila, coletar_candidatos(fila, buscar, escolhidas, memoria))
    busca_profunda.registrar(memoria, escolhidas, candidatos)
    busca_profunda.salvar(memoria)
    from . import variedade
    escolhidos = selecionar(candidatos, config.OFERTAS_POR_GARIMPO, variedade.contar_pendentes(fila))
    fontes_ia = 0
    for o in escolhidos:
        texto = legenda.gerar(o)
        o["titulo"], o["legenda"] = texto["titulo"], texto["legenda"]
        fontes_ia += texto["fonte"] == "ia"
        # a arte/Reels é gerada só na hora de postar (não ocupa espaço no repositório)
        o.update({"status": "pendente",
                  "criado_em": agora().strftime(FMT), "postado_em": "", "id_post": ""})
        fila["ofertas"][o["id"]] = o
        selo = SELO[o["nivel"]]
        print(f"{selo} {o['categoria']:<11} R$ {o['preco_fmt']:>8}  comissão R$ {o['comissao']:.2f} "
              f"({o['comissao_pct']:.0f}%)  {o['vendas']} vendas  uau {o['uau']:.0f}  {o['titulo']}")
    try:
        from . import pedidos
        pedidos.atender(fila)
    except Exception as e:
        print(f"::warning::Pedidos do Zé não foram atendidos: {e}")
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
