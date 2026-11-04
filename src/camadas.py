"""Duas camadas de produto no Garimpo VIP (04/11/2026, pedido do Fred: "temos que ter produtos conhecidos também,
precisamos de volume e diversidade, e os especiais devem ter destaque").

⭐ ESPECIAL — o achado de verdade (uau 8+, foto aprovada; é a regra da curadoria nova de 02/11/2026).
   Ganha o selo dourado "ACHADO DO ZÉ", abre o carrossel (capa) e é o único que vira Reels.
🏷️ CONHECIDO — produto que o público já conhece e confia, para dar volume e variedade:
   - marca famosa no nome (JBL, Anker, Xiaomi, Tramontina, Philips...), com uau a partir de 5
     (liquidificador Tramontina entra aqui, mas nunca como especial);
   - loja oficial da Awin (Arno, Shark Ninja, VX Case) com uau a partir de 5;
   - mais vendido do Mercado Livre no lançamento (até config.ML_LANCAMENTO_ATE);
   - campeão de vendas (10 mil+ vendidos, nota 4,8+) com algum detalhe esperto (uau 6+).
   Vai para o Telegram e o WhatsApp e completa os carrosséis com a arte normal (sem selo), atrás dos especiais.

Produto genérico sem marca e sem nada de especial (varal, pote) continua de fora, como antes.
Liga com CAMADAS=1 (variável do GitHub); com 0 o robô segue só com os especiais.
"""
import os
import re

from . import config, curadoria, marcas, variedade


def ligado():
    return config.PERFIL == "garimpo" and os.getenv("CAMADAS", "0") == "1"


UAU_CONHECIDO = float(os.getenv("UAU_CONHECIDO", "5"))
CAMPEAO_VENDAS = int(os.getenv("CAMPEAO_VENDAS", "10000"))
CAMPEAO_NOTA = float(os.getenv("CAMPEAO_NOTA", "4.8"))
CAMPEAO_UAU = float(os.getenv("CAMPEAO_UAU", "6"))
CONHECIDOS_POR_GARIMPO = int(os.getenv("CONHECIDOS_POR_GARIMPO", "8"))     # novos conhecidos na fila por rodada
CONHECIDOS_POR_CARROSSEL = int(os.getenv("CONHECIDOS_POR_CARROSSEL", "2"))  # no carrossel de 4: no máximo 2
ESPECIAIS_POR_CARROSSEL_MIN = int(os.getenv("ESPECIAIS_POR_CARROSSEL_MIN", "1"))  # sem especial, não tem carrossel
WHATSAPP_CONHECIDOS_POR_DIA = int(os.getenv("WHATSAPP_CONHECIDOS_POR_DIA", "2"))

# Marcas que o brasileiro conhece e confia (como aparecem no nome do anúncio). Nome curto demais ou que vira
# palavra comum ("LG", "Mi", "Estrela", "Gama") fica de fora para não pegar produto errado.
MARCAS_CONHECIDAS = [
    # som, celular e tecnologia
    "JBL", "Anker", "Soundcore", "Xiaomi", "Redmi", "Samsung", "Motorola", "Lenovo", "Philips", "Sony",
    "Logitech", "Baseus", "Ugreen", "Edifier", "QCY", "Haylou", "Amazfit", "Huawei", "Realme", "TP-Link",
    "Intelbras", "Multilaser", "Positivo", "Kingston", "SanDisk", "Havit", "Redragon", "HyperX", "Razer",
    "Pioneer", "Knup", "Geonav", "i2GO",
    # casa e cozinha
    "Tramontina", "Electrolux", "Mondial", "Britania", "Britânia", "Philco", "Oster", "Arno", "WAP", "Black+Decker",
    "Black Decker", "Stanley", "Brinox", "Rochedo", "Midea", "Cadence", "Termolar", "Tupperware",
    "Panasonic", "Consul", "Brastemp", "Fischer", "Nespresso", "Polishop",
    "Mallory", "Agratto", "Lenoxx", "Elgin", "Coza", "Euro Home", "Wolff", "Tefal",
    # beleza e cuidados
    "Taiff", "Gama Italy", "Wahl", "Braun", "Remington", "Lizze", "Salon Line", "Vult", "Boticário", "Boticario",
    "Natura", "Ruby Rose", "Max Love", "Océane", "Oceane", "Eudora", "Conair", "Babyliss",
    # ferramentas e carro
    "Bosch", "Makita", "Dewalt", "Vonder", "Einhell", "Wesco", "Worx", "Tekbond", "Starrett", "Michelin",
    "Black & Decker", "Gedore", "Irwin",
    # bebê, criança e pet
    "Fisher-Price", "Fisher Price", "Chicco", "Burigotto", "Galzerano", "Multikids", "Safety 1st", "Buba",
    "Pedigree", "Whiskas", "Petlon", "Chalesco",
    # garrafa, mochila, esporte
    "Contigo", "Hydro Flask", "Samsonite", "Xtrad",
]
# Marca muito falsificada na Shopee: só conta se a loja for a oficial (nome da loja com a marca ou "oficial")
FALSIFICADAS = {"jbl", "stanley", "sony", "samsung", "contigo", "hydro flask", "tupperware", "wahl", "babyliss",
                "boticario", "natura", "nespresso"}
# Palavras que, logo antes da marca, mostram que o produto NÃO é dela ("capinha para Xiaomi", "tipo JBL")
_NAO_E_DA_MARCA = {"para", "pra", "compativel", "compatível", "tipo", "estilo", "similar", "modelo", "igual",
                   "imitacao", "réplica", "replica", "linha", "serve"}

_RE = None


def _regex():
    global _RE
    if _RE is None:
        termos = sorted({" ".join(curadoria._norm(m)) for m in MARCAS_CONHECIDAS if curadoria._norm(m)}, key=len, reverse=True)
        _RE = re.compile(r"(?:^| )(" + "|".join(re.escape(t) for t in termos) + r")(?= |$)")
    return _RE


def marca_conhecida(o):
    """Nome da marca famosa que aparece no anúncio (ou ""). Ignora "capinha para Xiaomi", "caixa tipo JBL"."""
    nome = o if isinstance(o, str) else o.get("nome", "")
    bruto = curadoria._norm(nome)
    txt = " ".join(bruto)
    for m in _regex().finditer(txt):
        antes = txt[: m.start()].split()[-2:]
        if any(p in _NAO_E_DA_MARCA for p in antes):
            continue
        if m.group(1) in FALSIFICADAS and not isinstance(o, str):
            loja = " ".join(curadoria._norm(o.get("loja") or ""))
            if m.group(1) not in loja and "oficial" not in loja and "official" not in loja:
                continue
        return m.group(1)
    if not isinstance(o, str):   # loja com o nome da marca ("JBL Oficial", "Xiaomi Store BR")
        loja = " ".join(curadoria._norm(o.get("loja") or ""))
        m = _regex().search(loja)
        if m:
            return m.group(1)
    return ""


def _hoje():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d")


def especial(o):
    """⭐ Achado do Zé: o que a curadoria nova manda para o Instagram (uau 8+, foto aprovada)."""
    return variedade.para_instagram(o)


def _foto_ok(o):
    return o.get("foto_nota") is None or o["foto_nota"] >= config.FOTO_MINIMA


def motivo_conhecido(o):
    """Por que entra como 🏷️ conhecido ("marca JBL", "loja oficial Arno", "campeão de vendas"...), ou ""."""
    if "gancho" not in o or especial(o) or not _foto_ok(o):   # sem "gancho" = julgado pela regra antiga
        return ""
    u = variedade.uau(o)   # já com as travas: franquia 0, casa comum no máximo 5, vitrine no máximo 6
    if u >= UAU_CONHECIDO:
        if marcas.eh_marca(o):
            return f"loja oficial {marcas.nome(o)}"
        if o.get("lancamento_ml") and str(o.get("criado_em") or _hoje())[:10] <= config.ML_LANCAMENTO_ATE:
            return "mais vendido do Mercado Livre"
        m = marca_conhecida(o)
        if m:
            return f"marca {m.upper() if len(m) <= 4 else m.title()}"
    if (u >= CAMPEAO_UAU and (o.get("vendas") or 0) >= CAMPEAO_VENDAS
            and (o.get("nota") or 0) >= CAMPEAO_NOTA):
        return "campeão de vendas"
    return ""


def conhecido(o):
    return ligado() and bool(motivo_conhecido(o))


def camada(o):
    if especial(o):
        return "especial"
    return "conhecido" if conhecido(o) else ""


def selo_ze(o):
    """Ganha o selo dourado "ACHADO DO ZÉ"? (o 💎 achado escondido já tem o selo dele)."""
    return ligado() and o.get("nivel") != "achado" and especial(o)
