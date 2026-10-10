"""Preço honesto: confere o preço na Shopee pouco antes de postar e evita "de/por" exagerado.

- conferir(oferta): busca o produto de novo na API. Se o preço mudou, atualiza oferta, arte e legenda.
  Devolve "ok", "mudou", "subiu" (ficou >15% mais caro: deixou de ser achado) ou "sumiu" (fora do ar).
- ajustar_de(oferta): só mostra "de R$ X por R$ Y" quando o desconto é crível (até 60%).
- aviso(oferta): linha curta para a legenda dizendo quando o preço foi conferido.
"""
import re


def agora():
    from .garimpar import agora as _a
    return _a()


DESCONTO_MAX_EXIBIDO = 60     # acima disso o "preço de" da loja costuma ser inflado
SUBIDA_MAX = 1.15             # subiu mais que 15% desde o garimpo → não posta


def brl(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ajustar_de(o):
    if not o.get("preco_de") or not (5 <= (o.get("desconto") or 0) <= DESCONTO_MAX_EXIBIDO):
        o["preco_de"], o["desconto"] = None, 0
    return o


def tem_variacoes(o):
    return bool(o.get("preco_max")) and o["preco_max"] > (o.get("preco") or 0) * 1.05


def _trocar_na_legenda(o, antigo_fmt, desconto_antigo):
    leg = o.get("legenda") or ""
    if antigo_fmt and antigo_fmt != o["preco_fmt"]:
        leg = leg.replace(antigo_fmt, o["preco_fmt"])
    novo = o.get("desconto") or 0
    if desconto_antigo and desconto_antigo != novo:
        if novo:
            leg = re.sub(rf"(?<!\d){desconto_antigo}\s?%", f"{novo}%", leg)
        else:   # some o desconto inflado: "com 86% de desconto", "(86% OFF)", "-86%"
            leg = re.sub(rf"\s*(com\s+)?\(?-?(?<!\d){desconto_antigo}\s?%(\s*(de\s+desconto|off))?\)?",
                         "", leg, flags=re.I)
            leg = re.sub(r" +([.,!])", r"\1", leg)
    o["legenda"] = leg


def conferir(o):
    """Atualiza o preço com a API (só Shopee). Nunca derruba a postagem por falha da API."""
    antigo, antigo_fmt, desc_antigo = o.get("preco") or 0, o.get("preco_fmt"), o.get("desconto") or 0
    ajustar_de(o)
    o["preco_conferido_em"] = agora().strftime("%d/%m às %H:%M")
    situacao = "ok"
    if (o.get("plataforma") or "shopee") == "shopee" and not o.get("video_manual"):
        situacao = _consultar(o, antigo)
    if situacao in ("ok", "mudou"):
        _trocar_na_legenda(o, antigo_fmt, desc_antigo)
    return situacao


def _consultar(o, antigo):
    from . import shopee
    from .garimpar import normalizar
    try:
        nos = shopee.buscar_por_item(o["id"])
    except Exception as e:
        print(f"::warning::Não consegui conferir o preço de {o['id']} ({e}); seguindo com o do garimpo.")
        return "ok"
    if not nos:
        return "sumiu"
    novo = normalizar(nos[0], o["categoria"], o.get("palavra", ""))
    if novo["preco"] <= 0:
        return "sumiu"
    o["preco_max"] = novo.get("preco_max")
    if antigo and novo["preco"] > antigo * SUBIDA_MAX:
        print(f"📈 {o.get('titulo')}: subiu de R$ {brl(antigo)} para R$ {novo['preco_fmt']} — descartado.")
        return "subiu"
    mudou = abs(novo["preco"] - antigo) >= 0.01
    for k in ("preco", "preco_fmt", "preco_de", "desconto", "comissao"):
        o[k] = novo[k]
    if mudou:
        print(f"💱 {o.get('titulo')}: preço atualizado de R$ {brl(antigo)} para R$ {o['preco_fmt']}.")
    return "mudou" if mudou else "ok"


def aviso(o):
    loja = "AliExpress" if o.get("plataforma") == "aliexpress" else "Shopee"
    quando = o.get("preco_conferido_em") or agora().strftime("%d/%m às %H:%M")
    base = "Preço a partir de" if tem_variacoes(o) else "Preço"
    pix = " Pagando no Pix, a Shopee costuma dar desconto extra." if loja == "Shopee" else ""
    return f"🕒 {base} R$ {o['preco_fmt']}, conferido em {quando}.{pix} O preço pode mudar a qualquer momento."
