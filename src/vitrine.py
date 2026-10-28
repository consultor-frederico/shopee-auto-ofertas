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


def escolher(fila):
    corte = (agora() - timedelta(days=DIAS)).strftime(FMT)
    postados = [o for o in fila["ofertas"].values()
                if o.get("status") == "postado" and str(o.get("postado_em") or "") >= corte
                and o.get("link_afiliado") and o.get("imagem") and o.get("titulo")]
    return sorted(postados, key=lambda o: (o["postado_em"], o.get("postado_ts", 0)), reverse=True)[:MAX_ITENS]


def gerar():
    if config.PERFIL != "garimpo":
        return
    try:
        itens = [{"titulo": o["titulo"], "preco": o.get("preco_fmt"), "preco_de": o.get("preco_de"),
                  "imagem": o["imagem"], "link": vendas.do_canal(o, "bio"), "loja": o.get("loja") or "",
                  "plataforma": o.get("plataforma") or "shopee"}
                 for o in escolher(carregar_fila())]
        ARQ.write_text(json.dumps({"atualizado": agora().strftime(FMT), "itens": itens},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"🛍️ Vitrine da bio: {len(itens)} achados.")
    except Exception as e:   # a vitrine nunca pode derrubar um post
        print(f"::warning::Vitrine da bio não atualizou: {e}")


if __name__ == "__main__":
    gerar()
