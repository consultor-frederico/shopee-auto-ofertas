"""Vendas da Shopee Afiliados: links marcados por canal e relatório de pedidos.

Links por canal: cada link que sai do robô leva um subId com o perfil e o canal
(ex.: garimpo + igdm), gerado pela API (generateShortLink). Assim o painel da Shopee e o
relatório de conversões mostram de qual canal veio cada venda. Se a API falhar, usa o link
de afiliado normal (nunca deixa de mandar link). Desligar: LINKS_POR_CANAL=0.

Relatório: pedidos e comissão de um período (conversionReport), agrupados por canal, para o
status das 8h no Telegram privado.

Teste: python -m src.vendas   (mostra no log os pedidos dos últimos 30 dias e um link de teste)
"""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

from . import config, shopee

BRT = timezone(timedelta(hours=-3))
LIGADO = os.getenv("LINKS_POR_CANAL", "1") != "0"

# subId do canal → nome que aparece no status
CANAIS = {
    "igdm": "Instagram (QUERO no direct)",
    "igstory": "Instagram (story)",
    "igtop": "Instagram (Top 5/carrossel)",
    "zebusca": "Busca do Zé",
    "fbdm": "Facebook",
    "yt": "YouTube",
    "tg": "Telegram",
    "zap": "WhatsApp",
    "bio": "Página da bio",
}

_cache = {}       # só na memória da rodada: um arquivo dividido entre workflows daria conflito no git
_lojas = None


def _loja_da_fila(item_id):
    """Itens de carrossel/Top 5 guardam só o id: a loja vem da fila."""
    global _lojas
    if _lojas is None:
        try:
            _lojas = {k: v.get("loja_id") for k, v in
                      json.loads(config.ARQ_FILA.read_text(encoding="utf-8"))["ofertas"].items()}
        except Exception:
            _lojas = {}
    return _lojas.get(str(item_id))


def _sub(txt):
    return re.sub(r"[^A-Za-z0-9]", "", str(txt))[:20]


def link_curto(url_produto, sub_ids):
    sub = ",".join(json.dumps(_sub(s)) for s in sub_ids if _sub(s))
    q = (f'mutation{{generateShortLink(input:{{originUrl:{json.dumps(url_produto)},subIds:[{sub}]}})'
         f'{{shortLink}}}}')
    return ((shopee.consultar(q, tentativas=2).get("generateShortLink") or {}).get("shortLink")) or ""


def _url_produto(o):
    item = str(o.get("id") or "")
    loja = o.get("loja_id") or (_loja_da_fila(item) if item.isdigit() else None)
    if loja and item.isdigit():
        return f"https://shopee.com.br/product/{int(loja)}/{int(item)}"
    return ""


def do_canal(o, canal):
    """Link de afiliado da oferta marcado com o canal. Fora da Shopee (Awin, AliExpress) ou se
    algo falhar, devolve o link de afiliado normal."""
    base = (o or {}).get("link_afiliado") or ""
    if not LIGADO or not base or (o.get("plataforma") or "shopee") != "shopee":
        return base
    url = _url_produto(o)
    if not url:
        return base
    chave = (url, config.PERFIL, canal)
    if chave in _cache:
        return _cache[chave]
    try:
        link = link_curto(url, [config.PERFIL, canal])
    except Exception as e:
        print(f"::warning::Link por canal falhou ({canal}): {str(e)[:160]} — usando o link normal.")
        return base
    if not link.startswith("https://"):
        return base
    _cache[chave] = link
    return link


# ---------------- relatório de pedidos ----------------

CAMPOS_CONVERSAO = ("purchaseTime conversionId totalCommission utmContent "
                    "orders{orderStatus items{itemName qty actualAmount itemTotalCommission}}")


def pedidos(inicio, fim):
    """Conversões entre dois datetimes (horário da compra)."""
    nos, scroll = [], None
    for _ in range(20):
        extra = f',scrollId:{json.dumps(scroll)}' if scroll else ""
        q = (f"query{{conversionReport(purchaseTimeStart:{int(inicio.timestamp())},"
             f"purchaseTimeEnd:{int(fim.timestamp())},limit:500{extra})"
             f"{{nodes{{{CAMPOS_CONVERSAO}}}pageInfo{{hasNextPage scrollId}}}}}}")
        raiz = shopee.consultar(q).get("conversionReport") or {}
        nos += raiz.get("nodes") or []
        info = raiz.get("pageInfo") or {}
        if not info.get("hasNextPage") or not info.get("scrollId"):
            break
        scroll = info["scrollId"]
        time.sleep(1)
    return nos


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def canal_da_venda(no):
    """utmContent traz os subIds separados por '-' (ex.: 'garimpo-igdm---')."""
    partes = [p for p in str(no.get("utmContent") or "").split("-") if p]
    perfil = next((p for p in partes if p in ("garimpo", "ana")), "")
    canal = next((CANAIS[p] for p in partes if p in CANAIS), "sem marcação")
    return (f"{canal} ({'Ana' if perfil == 'ana' else 'Garimpo'})" if perfil else canal)


def resumo(dias=1, agora=None):
    """(linhas, totais) dos pedidos dos últimos `dias` dias."""
    agora = agora or datetime.now(BRT)
    nos = pedidos(agora - timedelta(days=dias), agora)
    por_canal = {}
    total_ped, total_com, total_valor = 0, 0.0, 0.0
    for no in nos:
        itens = [it for od in no.get("orders") or [] for it in od.get("items") or []]
        status = {str(od.get("orderStatus") or "").upper() for od in no.get("orders") or []}
        if status and status <= {"CANCELLED", "CANCELED", "UNPAID"}:
            continue
        com = _num(no.get("totalCommission"))
        valor = sum(_num(it.get("actualAmount")) for it in itens)
        c = por_canal.setdefault(canal_da_venda(no), [0, 0.0])
        c[0] += 1
        c[1] += com
        total_ped += 1
        total_com += com
        total_valor += valor
    linhas = [f"  {nome}: {n} pedido{'s' if n != 1 else ''}, R$ {com:.2f}".replace(".", ",")
              for nome, (n, com) in sorted(por_canal.items(), key=lambda x: -x[1][1])]
    return linhas, {"pedidos": total_ped, "comissao": total_com, "valor": total_valor}


def _brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def linha_status():
    """Bloco de vendas para o status das 8h: ontem e últimos 7 dias."""
    hoje = datetime.now(BRT).replace(hour=0, minute=0, second=0, microsecond=0)
    _, ontem = resumo(1, hoje)
    linhas7, sete = resumo(7, hoje)
    texto = [f"💰 <b>Vendas Shopee</b> — ontem: {ontem['pedidos']} pedido(s), {_brl(ontem['comissao'])} de comissão",
             f"   7 dias: {sete['pedidos']} pedido(s), {_brl(sete['comissao'])} de comissão, {_brl(sete['valor'])} vendidos"]
    if linhas7:
        texto += ["   por canal (7 dias):"] + linhas7
    return "\n".join(texto)


def main():
    agora = datetime.now(BRT)
    for dias in (1, 7, 30):
        try:
            linhas, tot = resumo(dias, agora)
            print(f"\n=== Últimos {dias} dias: {tot}")
            print("\n".join(linhas) or "  (nenhum pedido)")
        except Exception as e:
            print(f"❌ relatório {dias} dias: {str(e)[:500]}")
    try:
        nos = pedidos(agora - timedelta(days=30), agora)
        for n in nos[:5]:
            print("   " + json.dumps(n, ensure_ascii=False)[:400])
    except Exception as e:
        print(f"❌ {str(e)[:500]}")
    try:
        nos = shopee.buscar_ofertas("porta tempero", limite=1)
        o = {"id": str(nos[0]["itemId"]), "loja_id": nos[0]["shopId"], "link_afiliado": nos[0]["offerLink"]}
        print(f"\nLink normal: {o['link_afiliado']}")
        print(f"Link de teste marcado: {link_curto(_url_produto(o), [config.PERFIL, 'teste'])}")
    except Exception as e:
        print(f"❌ link por canal: {str(e)[:500]}")
    try:   # um item de carrossel (sem loja guardada) e para onde o link marcado leva
        import requests
        fila = json.loads(config.ARQ_FILA.read_text(encoding="utf-8"))["ofertas"]
        o = next(o for o in fila.values() if o.get("status") == "postado" and o.get("plataforma", "shopee") == "shopee")
        link = do_canal({"id": o["id"], "link_afiliado": o["link_afiliado"], "plataforma": "shopee"}, "teste")
        r = requests.get(link, timeout=30, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        print(f"\n{o['titulo']}: {link} → HTTP {r.status_code} {r.url[:200]}")
    except Exception as e:
        print(f"❌ do_canal: {str(e)[:300]}")
    try:
        print("\n" + linha_status())
    except Exception as e:
        print(f"❌ status: {str(e)[:500]}")


if __name__ == "__main__":
    main()
