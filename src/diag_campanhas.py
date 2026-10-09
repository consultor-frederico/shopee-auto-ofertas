"""Diagnóstico temporário: campanhas/cupons da Shopee na API de afiliados."""
import json

from . import config, shopee

saida = {}
for tipo in ("ShopeeOfferV2", "ShopeeOfferV2Node", "Query"):
    try:
        d = shopee.consultar('query{__type(name:"%s"){fields{name args{name}}}}' % tipo)
        saida[tipo] = (d.get("__type") or {}).get("fields")
    except Exception as e:
        saida[tipo] = str(e)
campos = "commissionRate imageUrl offerLink originalLink offerName offerType categoryId collectionId periodStartTime periodEndTime"
for nome, q in (("recentes", "sortType:1"), ("maior_comissao", "sortType:2")):
    for tentativa in (campos, "commissionRate imageUrl offerLink offerName periodStartTime periodEndTime"):
        try:
            d = shopee.consultar("query{shopeeOfferV2(%s,page:1,limit:30){nodes{%s}}}" % (q, tentativa))
            saida[nome] = d
            break
        except Exception as e:
            saida[nome] = str(e)
config.PASTA_DADOS.mkdir(exist_ok=True)
(config.PASTA_DADOS / "diag_campanhas.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1))
print("::notice::ok")
