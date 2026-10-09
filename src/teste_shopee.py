"""Testa recursos da API de afiliados da Shopee para o garimpo profundo.

Uso: python -m src.teste_shopee  (o resultado vai para a tela e para data/relatorios/teste_shopee.txt)
"""
import json

from . import shopee

BASE = ("itemId productName priceMin commission commissionRate sales ratingStar shopName "
        "shopId productCatIds")


def tentar(nome, query):
    print(f"\n=== {nome}\n{query[:220]}")
    try:
        dados = shopee.consultar(query)
    except Exception as e:
        print(f"❌ {e}"[:600])
        return None
    raiz = next(iter(dados.values()), None) if dados else None
    nos = (raiz or {}).get("nodes") or []
    print(f"✅ {len(nos)} itens | pageInfo: {(raiz or {}).get('pageInfo')}")
    for n in nos[:6]:
        print("   " + json.dumps(n, ensure_ascii=False)[:300])
    return nos


def main():
    nos = tentar("Busca comum (controle)",
                 f'query{{productOfferV2(keyword:"porta tempero",sortType:2,page:1,limit:10){{nodes{{{BASE}}}}}}}')
    shop_id = (nos or [{}])[0].get("shopId")
    cats = (nos or [{}])[0].get("productCatIds") or []
    tentar("Comissão extra do vendedor (isAMSOffer)",
           f'query{{productOfferV2(keyword:"porta tempero",isAMSOffer:true,sortType:5,page:1,limit:10)'
           f'{{nodes{{{BASE}}}pageInfo{{page limit hasNextPage}}}}}}')
    tentar("Vendedores-chave (isKeySeller)",
           f'query{{productOfferV2(keyword:"porta tempero",isKeySeller:true,sortType:2,page:1,limit:10)'
           f'{{nodes{{{BASE}}}}}}}')
    for lt, nome in ((1, "Top performing"), (2, "Landing category")):
        tentar(f"Lista {nome} (listType:{lt})",
               f'query{{productOfferV2(listType:{lt},sortType:2,page:1,limit:10){{nodes{{{BASE}}}}}}}')
    if shop_id:
        tentar(f"Outros produtos da loja {shop_id} (shopId)",
               f'query{{productOfferV2(shopId:{shop_id},sortType:2,page:1,limit:10){{nodes{{{BASE}}}}}}}')
    for c in cats[-2:]:
        tentar(f"Por categoria {c} (productCatId)",
               f'query{{productOfferV2(productCatId:{c},sortType:2,page:1,limit:10){{nodes{{{BASE}}}}}}}')
    tentar("Lojas com comissão (shopOfferV2)",
           'query{shopOfferV2(keyword:"utilidades",sortType:2,page:1,limit:5)'
           '{nodes{shopId shopName commissionRate ratingStar shopType}}}')


if __name__ == "__main__":
    main()
