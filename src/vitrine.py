"""Vitrine da página da bio (garimpovipbr.github.io): os últimos achados postados no Instagram.

Grava data/vitrine.json, que a página da bio lê direto do GitHub. Cada link vai marcado com o
canal "bio" (vendas.do_canal), para o relatório de vendas mostrar quem comprou pela bio.
Roda no fim de cada post do Garimpo VIP (postar e carrossel de achados).

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


def gerar():
    if config.PERFIL != "garimpo":
        return
    try:
        fila = carregar_fila()
        antigos = {}
        if ARQ.exists():
            antigos = {str(b["num"]): b["link"] for b in json.loads(ARQ.read_text(encoding="utf-8")).get("busca", [])}
        busca = _numerados(fila, antigos)
        links = {b["num"]: b["link"] for b in busca}
        itens = [{"titulo": o["titulo"], "preco": o.get("preco_fmt"), "preco_de": o.get("preco_de"),
                  "imagem": o["imagem"], "link": links.get(o.get("num")) or vendas.do_canal(o, "bio"),
                  "loja": o.get("loja") or "", "plataforma": o.get("plataforma") or "shopee", "num": o.get("num")}
                 for o in escolher(fila)]
        ARQ.write_text(json.dumps({"atualizado": agora().strftime(FMT), "itens": itens, "busca": busca},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"🛍️ Vitrine da bio: {len(itens)} achados; {len(busca)} na busca por número.")
    except Exception as e:   # a vitrine nunca pode derrubar um post
        print(f"::warning::Vitrine da bio não atualizou: {e}")


if __name__ == "__main__":
    gerar()
