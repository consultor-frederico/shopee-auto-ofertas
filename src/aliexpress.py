"""API de Afiliados da AliExpress (aliexpress.affiliate.product.query).

Segredos: ALIEXPRESS_APP_KEY, ALIEXPRESS_APP_SECRET e ALIEXPRESS_TRACKING_ID (o "Tracking ID" do
portal de afiliados). Sem eles, o robô simplesmente não busca na AliExpress.

Filtro pedido pelo Fred: só produto que chega rápido ao Brasil (entrega em até 7 dias),
de vendedor bem avaliado e com comissão alta.
"""
import hashlib
import hmac
import json
import os
import time

import requests

URL = "https://api-sg.aliexpress.com/sync"
METODO_BUSCA = "aliexpress.affiliate.product.query"
METODO_EM_ALTA = "aliexpress.affiliate.hotproduct.query"   # produtos em alta (lista separada)
DIAS_ENTREGA_MAX = 7          # "já está no Brasil": entrega rápida para o Brasil
AVALIACAO_MIN_PCT = 95.0      # vendedor confiável: ≥ 95% de avaliações positivas


def _env(nome):
    return (os.getenv(nome) or "").strip()


def configurado():
    return all(_env(n) for n in ("ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET", "ALIEXPRESS_TRACKING_ID"))


def assinar(params, segredo):
    """HMAC-SHA256 (hex maiúsculo) sobre chave+valor dos parâmetros em ordem alfabética."""
    base = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(segredo.encode(), base.encode(), hashlib.sha256).hexdigest().upper()


def chamar(metodo, **negocio):
    params = {"app_key": _env("ALIEXPRESS_APP_KEY"), "method": metodo, "sign_method": "sha256",
              "timestamp": str(int(time.time() * 1000)), "format": "json", "v": "2.0"}
    params.update({k: str(v) for k, v in negocio.items() if v is not None})
    params["sign"] = assinar(params, _env("ALIEXPRESS_APP_SECRET"))
    r = requests.post(URL, data=params, timeout=40,
                      headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"})
    r.raise_for_status()
    dados = r.json()
    if "error_response" in dados:
        e = dados["error_response"]
        raise RuntimeError(f"AliExpress: {e.get('code')} {e.get('msg')} {e.get('sub_msg', '')}".strip())
    return dados


def _pct(v):
    try:
        return float(str(v).replace("%", "").strip() or 0)
    except ValueError:
        return 0.0


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


_sem_permissao = set()   # métodos que a conta ainda não liberou (ex.: lista "em alta")


def buscar_produtos(palavra, pagina=1, ordem="LAST_VOLUME_DESC", limite=50, metodo=METODO_BUSCA):
    """Produtos crus da API (lista de dicionários). metodo: busca comum ou METODO_EM_ALTA."""
    if metodo in _sem_permissao:
        return []
    try:
        dados = _chamar_busca(metodo, palavra, pagina, ordem, limite)
    except RuntimeError as e:
        if metodo != METODO_BUSCA and "InsufficientPermission" in str(e):
            _sem_permissao.add(metodo)
            print(f"ℹ️  AliExpress: a lista '{metodo}' ainda não foi liberada para a conta — seguindo só com a busca.")
            return []
        raise
    return _produtos(dados, metodo)


def _chamar_busca(metodo, palavra, pagina, ordem, limite):
    return chamar(metodo, keywords=palavra, page_no=pagina, page_size=limite, sort=ordem,
                   target_currency="BRL", target_language="PT", ship_to_country="BR",
                   delivery_days=DIAS_ENTREGA_MAX, tracking_id=_env("ALIEXPRESS_TRACKING_ID"),
                   fields=("product_id,product_title,product_main_image_url,product_video_url,"
                           "target_sale_price,target_original_price,discount,evaluate_rate,"
                           "lastest_volume,commission_rate,hot_product_commission_rate,"
                           "promotion_link,shop_name,shop_id,ship_to_days"))


def _produtos(dados, metodo):
    resp = (dados.get(metodo.replace(".", "_") + "_response") or {}).get("resp_result") or {}
    if str(resp.get("resp_code")) not in ("200", "None") and resp.get("resp_code") is not None:
        raise RuntimeError(f"AliExpress resp_code {resp.get('resp_code')}: {resp.get('resp_msg')}")
    produtos = ((resp.get("result") or {}).get("products") or {}).get("product") or []
    if metodo == METODO_EM_ALTA:   # garante a regra "já está no Brasil" mesmo se a lista ignorar o filtro
        produtos = [p for p in produtos if 0 < _num(p.get("ship_to_days")) <= DIAS_ENTREGA_MAX]
    return produtos


def normalizar(p, categoria, palavra):
    """Converte para o mesmo formato das ofertas da Shopee (ver garimpar.normalizar)."""
    preco = _num(p.get("target_sale_price"))
    preco_de = _num(p.get("target_original_price"))
    desconto = int(_pct(p.get("discount")))
    if not (5 <= desconto <= 60) or preco_de <= preco:   # "de" acima de 60% costuma ser inflado
        preco_de, desconto = None, 0
    pct = max(_pct(p.get("commission_rate")), _pct(p.get("hot_product_commission_rate")))
    avaliacao = _pct(p.get("evaluate_rate"))
    return {
        "id": f"ae{p.get('product_id')}",
        "nome": (p.get("product_title") or "").strip(),
        "categoria": categoria,
        "palavra": palavra,
        "preco": preco,
        "preco_fmt": f"{preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "preco_de": round(preco_de, 2) if preco_de else None,
        "desconto": desconto,
        "comissao": round(preco * pct / 100, 2),
        "comissao_pct": round(pct, 1),
        "vendas": int(_num(p.get("lastest_volume"))),
        # % de avaliações positivas → escala de 5 estrelas (95% = 4,75), para usar o mesmo filtro
        "nota": round(avaliacao / 20, 2) if avaliacao else 0.0,
        "avaliacao_pct": avaliacao,
        "entrega_dias": int(_num(p.get("ship_to_days"))) or None,
        "loja": p.get("shop_name") or "",
        "plataforma": "aliexpress",
        "imagem": p.get("product_main_image_url") or "",
        "video": p.get("product_video_url") or "",
        "link_afiliado": p.get("promotion_link") or "",
    }


def recusa_extra(o):
    """Regras só da AliExpress, além do filtro geral."""
    if o.get("avaliacao_pct", 0) < AVALIACAO_MIN_PCT:
        return "vendedor pouco avaliado"
    if o.get("entrega_dias") and o["entrega_dias"] > DIAS_ENTREGA_MAX:
        return "entrega demorada"
    return None


if __name__ == "__main__":   # teste: python -m src.aliexpress "fone bluetooth"
    import sys
    palavra = sys.argv[1] if len(sys.argv) > 1 else "fone bluetooth"
    if not configurado():
        print("⏸️  Segredos da AliExpress ainda não cadastrados.")
        sys.exit(0)
    try:
        produtos = buscar_produtos(palavra, limite=20)
        em_alta = buscar_produtos(palavra, limite=20, metodo=METODO_EM_ALTA)
        print(f"🔥 Em alta: {len(em_alta)} produtos")
        for p in em_alta[:5]:
            o = normalizar(p, "teste", palavra)
            print(f"::notice::[EM ALTA] {o['nome'][:60]} | R$ {o['preco_fmt']} | {o['vendas']} vendas | "
                  f"comissão {o['comissao_pct']}%")
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
    print(f"🔎 '{palavra}': {len(produtos)} produtos com entrega em até {DIAS_ENTREGA_MAX} dias")
    for p in produtos[:10]:
        o = normalizar(p, "teste", palavra)
        print(f"::notice::{o['nome'][:60]} | R$ {o['preco_fmt']} | {o['vendas']} vendas | "
              f"{o['avaliacao_pct']}% positivas | comissão {o['comissao_pct']}% (R$ {o['comissao']}) | "
              f"entrega {o['entrega_dias'] or '?'}d | link {'ok' if o['link_afiliado'] else 'FALTA'}")
    print(json.dumps(produtos[:1], ensure_ascii=False)[:1500])
