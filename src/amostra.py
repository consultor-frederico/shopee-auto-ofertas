"""Amostra temporária: coleta ofertas de todos os nichos para calibrar os filtros."""
import csv
import time

from . import config, shopee
from .garimpar import normalizar

linhas, vistos = [], set()
for cat, palavras in config.NICHO.items():
    for p in palavras:
        for ordem in (2, 5):
            try:
                nos = shopee.buscar_ofertas(p, ordem=ordem, limite=50)
            except Exception as e:
                print("erro", p, e)
                continue
            for no in nos:
                o = normalizar(no, cat, p)
                if o["id"] in vistos:
                    continue
                vistos.add(o["id"])
                linhas.append({k: o[k] for k in ("id", "categoria", "palavra", "nome", "preco", "comissao",
                                                  "comissao_pct", "vendas", "nota", "desconto")})
            time.sleep(0.5)
config.PASTA_DADOS.mkdir(exist_ok=True)
with open(config.PASTA_DADOS / "amostra.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(linhas[0]))
    w.writeheader()
    w.writerows(linhas)
print(f"::notice::{len(linhas)} produtos coletados")
