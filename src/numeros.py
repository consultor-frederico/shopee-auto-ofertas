"""Número do achado (31/10/2026): cada produto que sai no feed do Garimpo VIP ganha um número curto e fixo
(#142). No TikTok e no YouTube o link não é clicável: a pessoa digita o número na página da bio
(garimpovipbr.github.io), que acha o produto em data/vitrine.json (src/vitrine.py).

O contador fica em data/numeros.json; o número vai junto da oferta (campo "num").
"""
import json

from . import config

ARQ = config.RAIZ / "data" / "numeros.json"


def numerar(oferta):
    """Dá o próximo número à oferta (se ela ainda não tem) e devolve o número. A Ana não numera."""
    if config.PERFIL != "garimpo":
        return None
    if oferta.get("num"):
        return oferta["num"]
    dados = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {"ultimo": 100}
    dados["ultimo"] = int(dados.get("ultimo", 100)) + 1
    ARQ.write_text(json.dumps(dados), encoding="utf-8")
    oferta["num"] = dados["ultimo"]
    return oferta["num"]
