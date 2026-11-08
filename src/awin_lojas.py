"""Lista as lojas da Awin que têm feed de produtos (inscritas ou não), para achar marcas novas.

Usa a mesma chave que já está dentro do AWIN_FEED_URL (lista oficial de feeds da Awin).
Só lê e mostra no log; não grava, não posta, não pede parceria. A chave nunca aparece no log.
Teste: python -m src.awin_lojas   (com AWIN_FEED_URL)
"""
import csv
import io
import re
import sys
from collections import defaultdict

import requests

from src import config
from src.awin import _texto


def main():
    m = re.search(r"/apikey/([^/?]+)", config.AWIN_FEED_URL or "")
    if not m:
        print("::error::Não achei a chave dentro do AWIN_FEED_URL.")
        sys.exit(1)
    try:
        r = requests.get(f"https://productdata.awin.com/datafeed/list/apikey/{m.group(1)}", timeout=90)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"::error::Awin: falha ao baixar a lista de feeds ({type(e).__name__}).")
        sys.exit(1)
    texto = _texto(r.content)
    linhas = list(csv.DictReader(io.StringIO(texto)))
    if not linhas:
        print("Lista vazia.")
        return
    print("Colunas:", list(linhas[0].keys()))
    lojas = defaultdict(lambda: {"produtos": 0, "feeds": 0})
    for l in linhas:
        l = {(k or "").strip().lower(): (v or "").strip() for k, v in l.items()}
        regiao = l.get("primary region", "")
        idioma = l.get("language", "")
        if regiao.upper() not in ("BR", "BRAZIL") and not idioma.lower().startswith("pt"):
            continue
        chave = (l.get("advertiser id", ""), l.get("advertiser name", ""))
        d = lojas[chave]
        d["status"] = l.get("membership status", "")
        d["setor"] = l.get("vertical", "")
        d["regiao"] = regiao
        d["atualizado"] = max(d.get("atualizado", ""), l.get("last imported", ""))
        d["feeds"] += 1
        try:
            d["produtos"] += int(l.get("no of products", "0") or 0)
        except ValueError:
            pass
    print(f"\n{len(lojas)} lojas do Brasil/português com feed:\n")
    for (aid, nome), d in sorted(lojas.items(), key=lambda x: (x[1]["status"], -x[1]["produtos"])):
        print(f"{d['status']:<12} | {aid:>7} | {nome[:40]:<40} | {d['produtos']:>7} produtos | "
              f"{d['setor'][:25]:<25} | {d['regiao']} | atualizado {d['atualizado']}")


if __name__ == "__main__":
    main()
