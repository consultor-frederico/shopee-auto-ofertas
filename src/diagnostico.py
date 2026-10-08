"""Diagnóstico: lista os campos disponíveis na API de afiliados (procura campos de vídeo)."""
from . import shopee

for tipo in ("ProductOfferV2", "ProductOfferV2Node", "ProductOffer"):
    try:
        d = shopee.consultar('query{__type(name:"%s"){name fields{name type{name kind ofType{name}}}}}' % tipo)
        t = d.get("__type")
        if t:
            print(f"== {tipo}:", ", ".join(f["name"] for f in t["fields"] or []))
    except Exception as e:
        print(f"== {tipo}: erro {e}")

for campo in ("videoUrl", "video", "videoInfo", "videos", "videoList", "imageUrls"):
    try:
        d = shopee.consultar('query{productOfferV2(limit:1){nodes{itemId %s}}}' % campo)
        print(f"campo {campo}: EXISTE ->", str(d)[:300])
    except Exception as e:
        print(f"campo {campo}: {str(e)[:160]}")
