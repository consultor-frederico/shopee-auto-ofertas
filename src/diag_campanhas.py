"""Diagnóstico temporário: campanhas/cupons da Shopee na API de afiliados."""
import json

from . import config, shopee

campos = "commissionRate offerLink originalLink offerName offerType collectionId periodStartTime periodEndTime"
saida = {}
for pagina in (2, 3, 4):
    try:
        saida[f"pagina{pagina}"] = shopee.consultar(
            "query{shopeeOfferV2(sortType:1,page:%d,limit:50){nodes{%s}}}" % (pagina, campos))
    except Exception as e:
        saida[f"pagina{pagina}"] = str(e)
for kw in ("cupom", "cupons", "frete", "11.11", "black", "oferta", "voucher", "desconto"):
    try:
        saida[f"kw_{kw}"] = shopee.consultar(
            'query{shopeeOfferV2(keyword:"%s",sortType:1,page:1,limit:50){nodes{%s}}}' % (kw, campos))
    except Exception as e:
        saida[f"kw_{kw}"] = str(e)
(config.PASTA_DADOS / "diag_campanhas.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1))
print("::notice::ok")
