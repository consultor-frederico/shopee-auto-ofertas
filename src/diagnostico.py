"""TEMPORÁRIO — amostra de todas as palavras-chave do perfil para calibrar o filtro."""
import json
import time

from . import config, curadoria, shopee
from .garimpar import motivo_recusa, normalizar

linhas, vistos = [], set()
for cat, palavras in config.NICHO.items():
    for palavra in palavras:
        for pagina, ordem in ((1, 2), (2, 2), (1, 5)):
            try:
                nos = shopee.buscar_ofertas(palavra, pagina=pagina, ordem=ordem)
            except Exception as e:
                print(f"erro {palavra}: {e}")
                continue
            for no in nos:
                o = normalizar(no, cat, palavra)
                if o["id"] in vistos:
                    continue
                vistos.add(o["id"])
                linhas.append({k: o[k] for k in ("id", "categoria", "palavra", "preco", "comissao",
                                                 "comissao_pct", "vendas", "nota", "desconto")}
                              | {"nome": o["nome"][:90], "motivo": motivo_recusa(o)})
            time.sleep(0.3)
passaram = [l for l in linhas if not l["motivo"]][:400]
notas = curadoria.notas_uau([{"id": l["id"], "nome": l["nome"]} for l in passaram])
for l in passaram:
    l["uau"] = notas.get(l["id"])
destino = config.PASTA_DADOS / "diag" / f"{config.PERFIL}.json"
destino.write_text(json.dumps(linhas, ensure_ascii=False), encoding="utf-8")
print(f"{config.PERFIL}: {len(linhas)} produtos, {len(passaram)} passaram no corte prata")
