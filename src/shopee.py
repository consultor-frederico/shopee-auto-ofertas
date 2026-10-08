"""Cliente da API de Afiliados da Shopee (GraphQL, assinatura SHA256)."""
import hashlib
import json
import time

import requests

from . import config

CAMPOS = ("itemId productName imageUrl offerLink productLink priceMin priceMax "
          "priceDiscountRate commission commissionRate sales ratingStar shopName")


class ErroShopee(RuntimeError):
    pass


def _assinatura(payload: str, timestamp: int) -> str:
    base = f"{config.SHOPEE_APP_ID}{timestamp}{payload}{config.SHOPEE_APP_SECRET}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def consultar(query: str) -> dict:
    if not config.SHOPEE_APP_ID or not config.SHOPEE_APP_SECRET:
        raise ErroShopee("Segredos SHOPEE_APP_ID / SHOPEE_APP_SECRET não configurados no GitHub.")
    payload = json.dumps({"query": query}, separators=(",", ":"))
    ts = int(time.time())
    headers = {
        "Authorization": f"SHA256 Credential={config.SHOPEE_APP_ID}, "
                         f"Signature={_assinatura(payload, ts)}, Timestamp={ts}",
        "Content-Type": "application/json",
    }
    resp = requests.post(config.SHOPEE_API_URL, headers=headers, data=payload, timeout=30)
    try:
        corpo = resp.json()
    except ValueError:
        raise ErroShopee(f"Resposta inválida da Shopee (HTTP {resp.status_code}): {resp.text[:300]}")
    if corpo.get("errors"):
        raise ErroShopee(f"Shopee retornou erro: {corpo['errors']}")
    return corpo.get("data") or {}


def buscar_ofertas(palavra: str, pagina: int = 1, limite: int = 50, ordem: int = 2) -> list:
    """ordem: 1 relevância, 2 mais vendidos, 3 maior preço, 4 menor preço, 5 maior comissão."""
    palavra_json = json.dumps(palavra, ensure_ascii=False)
    query = (f"query{{productOfferV2(keyword:{palavra_json},sortType:{ordem},"
             f"page:{pagina},limit:{limite}){{nodes{{{CAMPOS}}}}}}}")
    dados = consultar(query)
    return (dados.get("productOfferV2") or {}).get("nodes") or []


def buscar_por_item(item_id) -> list:
    """Oferta de um produto específico (pelo ID do item)."""
    query = f"query{{productOfferV2(itemId:{int(item_id)},limit:1){{nodes{{{CAMPOS}}}}}}}"
    dados = consultar(query)
    return (dados.get("productOfferV2") or {}).get("nodes") or []
