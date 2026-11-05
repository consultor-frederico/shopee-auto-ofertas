"""Vitrine da página da bio (garimpovipbr.github.io): os últimos achados postados no Instagram.

Grava data/vitrine.json, que a página da bio lê direto do GitHub. Cada link vai marcado com o
canal "bio" (vendas.do_canal), para o relatório de vendas mostrar quem comprou pela bio.
Roda no fim de cada post do Garimpo VIP (postar e carrossel de achados).

Busca pelo número (05/11/2026, Fred: "tem que achar do primeiro até o último"): todo achado com número
que foi postado fica guardado para sempre em data/numeros_hist.json, que a página lê quando a pessoa busca.
O link de afiliado da Shopee tem prazo: o robô renova os links com mais de DIAS_LINK dias.

Teste: python -m src.vitrine
"""
import json
from datetime import timedelta

from . import config, vendas
from .garimpar import FMT, agora, carregar_fila

ARQ = config.RAIZ / "data" / "vitrine.json"
MAX_ITENS = 12
DIAS = 4
DIAS_BUSCA = 30     # a busca pelo número do achado (#142) acha os produtos dos últimos 30 dias
MAX_BUSCA = 400
ARQ_HIST = config.RAIZ / "data" / "numeros_hist.json"   # todos os números já postados (nunca apaga)
DIAS_LINK = 25        # link da Shopee com mais de 25 dias é trocado por um novo
MAX_RENOVA = 40       # links renovados por rodada (não pesa na API da Shopee)


def escolher(fila):
    corte = (agora() - timedelta(days=DIAS)).strftime(FMT)
    postados = [o for o in fila["ofertas"].values()
                if o.get("status") == "postado" and str(o.get("postado_em") or "") >= corte
                and o.get("link_afiliado") and o.get("imagem") and o.get("titulo")]
    return sorted(postados, key=lambda o: (o["postado_em"], o.get("postado_ts", 0)), reverse=True)[:MAX_ITENS]


def _numerados(fila, antigos):
    """Busca pelo número do achado (31/10/2026): os produtos com número postados nos últimos DIAS_BUSCA dias.
    O link de cada número fica guardado (antigos) para não pedir um link novo à Shopee a cada post."""
    corte = (agora() - timedelta(days=DIAS_BUSCA)).strftime(FMT)
    lista = sorted((o for o in fila["ofertas"].values()
                    if o.get("num") and o.get("status") == "postado" and str(o.get("postado_em") or "") >= corte
                    and o.get("link_afiliado") and o.get("imagem")), key=lambda o: -int(o["num"]))[:MAX_BUSCA]
    return [{"num": o["num"], "titulo": o.get("titulo") or o.get("nome", ""), "preco": o.get("preco_fmt"),
             "imagem": o["imagem"], "plataforma": o.get("plataforma") or "shopee",
             "link": antigos.get(str(o["num"])) or vendas.do_canal(o, "bio")} for o in lista]


def _historico(fila, busca):
    """Junta os números postados ao histórico permanente e renova os links velhos da Shopee."""
    hist = json.loads(ARQ_HIST.read_text(encoding="utf-8")) if ARQ_HIST.exists() else {"itens": {}}
    todos = hist.setdefault("itens", {})
    links = {str(b["num"]): b["link"] for b in busca}
    agora_s = agora().strftime(FMT)
    for o in fila["ofertas"].values():
        if not (o.get("num") and o.get("status") == "postado" and o.get("imagem") and o.get("link_afiliado")):
            continue
        n = str(o["num"])
        reg = todos.get(n)
        plat = o.get("plataforma") or "shopee"
        loja_id = o.get("loja_id") or (vendas._loja_da_fila(str(o.get("id") or "")) if plat == "shopee" else None)
        novo = {"num": int(n), "titulo": o.get("titulo") or o.get("nome", ""), "preco": o.get("preco_fmt"),
                "preco_de": o.get("preco_de"), "imagem": o["imagem"], "plataforma": plat,
                "id": str(o.get("id") or ""), "loja_id": loja_id or (reg or {}).get("loja_id"),
                "link_afiliado": o["link_afiliado"],
                "postado_em": str(o.get("postado_em") or (reg or {}).get("postado_em") or agora_s)}
        if reg:
            reg.update({k: v for k, v in novo.items() if v not in (None, "")})
        else:
            novo.update({"link": links.get(n) or o["link_afiliado"], "link_em": novo["postado_em"]})
            todos[n] = novo
    # 🔗 links da Shopee vencendo: pede um link novo (os mais antigos primeiro)
    corte = (agora() - timedelta(days=DIAS_LINK)).strftime(FMT)
    ontem = (agora() - timedelta(days=1)).strftime(FMT)
    velhos = sorted((r for r in todos.values() if r.get("plataforma") == "shopee" and str(r.get("link_em") or "") < corte
                     and str(r.get("link_tentou") or "") < ontem),   # falhou hoje: tenta de novo amanhã
                    key=lambda r: str(r.get("link_em") or ""))[:MAX_RENOVA]
    renovados = 0
    for r in velhos:
        if not r.get("loja_id") and r.get("id", "").isdigit():   # sem a loja não dá para pedir link novo
            try:
                from . import shopee
                nos = shopee.buscar_por_item(r["id"])
                if nos:
                    r["loja_id"] = nos[0].get("shopId")
                    r.pop("sumiu", None)
                else:
                    r["sumiu"] = agora_s   # a Shopee não acha mais o produto: a página avisa e oferece a Busca do Zé
            except Exception as e:
                print(f"::warning::Loja do achado Nº {r['num']} não veio: {str(e)[:120]}")
        link = vendas.do_canal(r, "bio")
        if link and link not in (r.get("link"), r.get("link_afiliado")):
            r.update({"link": link, "link_em": agora_s})
            renovados += 1
        else:
            r["link_tentou"] = agora_s
    hist["atualizado"] = agora_s
    ARQ_HIST.write_text(json.dumps(hist, ensure_ascii=False, indent=0), encoding="utf-8")
    if renovados:
        print(f"🔗 Busca da página: {renovados} link(s) da Shopee renovado(s).")
    return todos


def gerar():
    if config.PERFIL != "garimpo":
        return
    try:
        fila = carregar_fila()
        antigos = {}
        if ARQ.exists():
            antigos = {str(b["num"]): b["link"] for b in json.loads(ARQ.read_text(encoding="utf-8")).get("busca", [])}
        busca = _numerados(fila, antigos)
        try:
            hist = _historico(fila, busca)
            for b in busca:   # a vitrine usa o link mais novo do histórico
                b["link"] = (hist.get(str(b["num"])) or {}).get("link") or b["link"]
        except Exception as e:
            hist = {}
            print(f"::warning::Histórico dos números não atualizou: {e}")
        links = {b["num"]: b["link"] for b in busca}
        itens = [{"titulo": o["titulo"], "preco": o.get("preco_fmt"), "preco_de": o.get("preco_de"),
                  "imagem": o["imagem"], "link": links.get(o.get("num")) or vendas.do_canal(o, "bio"),
                  "loja": o.get("loja") or "", "plataforma": o.get("plataforma") or "shopee", "num": o.get("num")}
                 for o in escolher(fila)]
        ARQ.write_text(json.dumps({"atualizado": agora().strftime(FMT), "itens": itens, "busca": busca},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"🛍️ Vitrine da bio: {len(itens)} achados; {len(busca)} na busca recente; {len(hist)} números no histórico.")
    except Exception as e:   # a vitrine nunca pode derrubar um post
        print(f"::warning::Vitrine da bio não atualizou: {e}")


if __name__ == "__main__":
    gerar()
