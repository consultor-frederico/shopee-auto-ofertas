"""Cliente da API de Afiliados da Shopee (GraphQL, assinatura SHA256)."""
import hashlib
import json
import time

import requests

from . import config

CAMPOS = ("itemId productName imageUrl offerLink productLink priceMin priceMax "
          "priceDiscountRate commission commissionRate sales ratingStar shopName shopId productCatIds")


class ErroShopee(RuntimeError):
    pass


def _assinatura(payload: str, timestamp: int) -> str:
    base = f"{config.SHOPEE_APP_ID}{timestamp}{payload}{config.SHOPEE_APP_SECRET}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


_ultima = [0.0]
INTERVALO_MIN = 0.4      # segundos entre chamadas (o garimpo profundo faz ~150 buscas por rodada)


def _limite_de_taxa(texto):
    t = str(texto).lower()
    return any(k in t for k in ("rate limit", "too many", "frequen", "limit exceeded", "10030", "429"))


def consultar(query: str, tentativas: int = 4) -> dict:
    if not config.SHOPEE_APP_ID or not config.SHOPEE_APP_SECRET:
        raise ErroShopee("Segredos SHOPEE_APP_ID / SHOPEE_APP_SECRET não configurados no GitHub.")
    payload = json.dumps({"query": query}, separators=(",", ":"))
    for n in range(tentativas):
        espera = INTERVALO_MIN - (time.time() - _ultima[0])
        if espera > 0:
            time.sleep(espera)
        _ultima[0] = time.time()
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
            corpo = {"errors": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        erro = corpo.get("errors") or (f"HTTP {resp.status_code}" if resp.status_code == 429 else None)
        if not erro:
            return corpo.get("data") or {}
        if _limite_de_taxa(erro) and n < tentativas - 1:
            pausa = 5 * (2 ** n)
            print(f"⏳ Shopee pediu para ir mais devagar — esperando {pausa}s ({erro})")
            time.sleep(pausa)
            continue
        raise ErroShopee(f"Shopee retornou erro: {erro}")
    raise ErroShopee("Shopee não respondeu depois de várias tentativas.")


def _nos(filtro: str, pagina: int, limite: int, ordem: int) -> list:
    query = (f"query{{productOfferV2({filtro}sortType:{ordem},"
             f"page:{pagina},limit:{limite}){{nodes{{{CAMPOS}}}}}}}")
    dados = consultar(query)
    return (dados.get("productOfferV2") or {}).get("nodes") or []


def buscar_ofertas(palavra: str, pagina: int = 1, limite: int = 50, ordem: int = 2, ams: bool = False) -> list:
    """ordem: 1 relevância, 2 mais vendidos, 3 maior preço, 4 menor preço, 5 maior comissão.
    ams=True: só ofertas em que o VENDEDOR paga comissão extra (costuma ser 20–40%)."""
    filtro = f"keyword:{json.dumps(palavra, ensure_ascii=False)}," + ("isAMSOffer:true," if ams else "")
    return _nos(filtro, pagina, limite, ordem)


def buscar_loja(shop_id, pagina: int = 1, limite: int = 50, ordem: int = 2) -> list:
    """Outros produtos de uma loja (para cavar nas lojas que já deram achado)."""
    return _nos(f"shopId:{int(shop_id)},", pagina, limite, ordem)


def buscar_categoria(cat_id, pagina: int = 1, limite: int = 50, ordem: int = 2, ams: bool = False) -> list:
    """Produtos de uma categoria da Shopee, sem palavra-chave."""
    return _nos(f"productCatId:{int(cat_id)}," + ("isAMSOffer:true," if ams else ""), pagina, limite, ordem)


def buscar_lojas(palavra: str, limite: int = 10) -> list:
    """Lojas com comissão (shopOfferV2): [{shopId, shopName, commissionRate, ratingStar}]."""
    query = (f"query{{shopOfferV2(keyword:{json.dumps(palavra, ensure_ascii=False)},sortType:2,page:1,"
             f"limit:{limite}){{nodes{{shopId shopName commissionRate ratingStar}}}}}}")
    return (consultar(query).get("shopOfferV2") or {}).get("nodes") or []


def buscar_por_item(item_id) -> list:
    """Oferta de um produto específico (pelo ID do item)."""
    query = f"query{{productOfferV2(itemId:{int(item_id)},limit:1){{nodes{{{CAMPOS}}}}}}}"
    dados = consultar(query)
    return (dados.get("productOfferV2") or {}).get("nodes") or []
