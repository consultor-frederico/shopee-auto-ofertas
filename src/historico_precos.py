"""📈 Histórico de preço (05/11/2026, ok do Fred): guarda 1 preço por dia de cada produto bom que o garimpo vê.

Serve para o Tatu Carão da Black Friday: dá para mostrar "esse aqui subiu antes da Black" ou "esse caiu de
verdade" com dado real, não com o "preço de" da loja. Grava em data/precos_hist.json:
  {"<id>": {"n": "nome curto", "p": [["2026-11-05", 39.9], ...]}}
Entra quem já está na fila ou quem passa no básico (nota >= 4,7 e 500+ vendas). Produto sem preço
novo há 60 dias sai do arquivo. Erro aqui nunca derruba o garimpo.

Consulta: python -m src.historico_precos <id>   (ou sem id: resumo do arquivo)
"""
import json
import sys
from datetime import date, timedelta

from . import config

ARQ = config.RAIZ / "data" / "precos_hist.json"
DIAS_GUARDA = 60
VENDAS_MIN = 500
NOTA_MIN = 4.7


def carregar():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar(d):
    ARQ.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _interessa(o, fila):
    if str(o.get("id")) in fila.get("ofertas", {}):
        return True
    return (o.get("vendas") or 0) >= VENDAS_MIN and (o.get("nota") or 0) >= NOTA_MIN


def anotar(d, o, hoje):
    preco = o.get("preco") or 0
    if preco <= 0 or not o.get("id"):
        return False
    reg = d.setdefault(str(o["id"]), {"n": (o.get("titulo") or o.get("nome") or "")[:60], "p": []})
    if reg["p"] and reg["p"][-1][0] == hoje:
        reg["p"][-1][1] = min(reg["p"][-1][1], round(preco, 2))   # várias vezes no dia: fica o menor
    else:
        reg["p"].append([hoje, round(preco, 2)])
    return True


def registrar(ofertas, fila, hoje=None):
    try:
        hoje = (hoje or date.today()).isoformat()
        d = carregar()
        n = sum(anotar(d, o, hoje) for o in ofertas if _interessa(o, fila))
        corte = (date.fromisoformat(hoje) - timedelta(days=DIAS_GUARDA)).isoformat()
        for k in [k for k, v in d.items() if not v["p"] or v["p"][-1][0] < corte]:
            del d[k]
        for v in d.values():
            v["p"] = [x for x in v["p"] if x[0] >= corte]
        salvar(d)
        return n
    except Exception as e:
        print(f"⚠️  Histórico de preço não gravou ({e})")
        return 0


def variacao(item_id, dias=30):
    """(menor, maior, atual) dos últimos `dias`, ou None se não houver histórico."""
    reg = carregar().get(str(item_id))
    if not reg:
        return None
    corte = (date.today() - timedelta(days=dias)).isoformat()
    ps = [p for d, p in reg["p"] if d >= corte] or [reg["p"][-1][1]]
    return min(ps), max(ps), reg["p"][-1][1]


if __name__ == "__main__":
    d = carregar()
    if len(sys.argv) > 1:
        print(json.dumps(d.get(sys.argv[1]), ensure_ascii=False, indent=1))
    else:
        dias = sorted({x[0] for v in d.values() for x in v["p"]})
        print(f"{len(d)} produtos, {sum(len(v['p']) for v in d.values())} preços, dias: {dias[:1]}…{dias[-1:]}")
