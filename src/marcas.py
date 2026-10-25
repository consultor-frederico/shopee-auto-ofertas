"""Marcas oficiais que entram pela Awin (src/awin.py). Cada marca é uma "plataforma" própria na fila.

Para incluir uma marca nova: aprovar o programa na Awin, marcar o anunciante no feed (Ferramentas → Crie um Feed,
o mesmo feed das outras) e acrescentar uma linha aqui. O resto do robô (arte, legenda, Telegram, limites diários)
lê esta tabela.

- anunciante: pedaços do nome do anunciante na coluna merchant_name do feed (sem acento, minúsculas)
- prefixo: começo do id na fila ("sn123"), para não misturar com ids da Shopee
- conferir_site: o feed da marca demora a atualizar, então o preço é conferido na loja (VTEX) antes de postar
- categoria: categoria fixa da marca (senão: cabelo vai para a Ana e o resto é "lar" no Garimpo VIP)
- preco_max: teto de preço só desta marca (as outras não têm teto)
- sem_licencas: produto de licença (Star Wars, Marvel, Harry Potter…: lista de franquias em variedade.py) fica de fora
"""

MARCAS = {
    "sharkninja": {"nome": "Shark Ninja", "loja": "Shark-Ninja BR", "cor": "#0B3C6F", "prefixo": "sn",
                   "anunciante": ("shark", "ninja"), "hashtag": "#sharkninja", "conferir_site": False},
    "arno": {"nome": "Arno", "loja": "Arno BR", "cor": "#C8102E", "prefixo": "ar",
             "anunciante": ("arno",), "hashtag": "#arno", "conferir_site": True},
    "lego": {"nome": "Lego", "loja": "Lego BR", "cor": "#D01012", "prefixo": "lg",
             "anunciante": ("lego",), "hashtag": "#lego", "conferir_site": False,
             "categoria": "brinquedos", "preco_max": 300, "sem_licencas": True},
}


def _plat(o):
    return o if isinstance(o, str) else (o.get("plataforma") or "shopee")


def eh_marca(o):
    """True se a oferta (ou o nome da plataforma) é de marca oficial: sem nota nem vendas."""
    return _plat(o) in MARCAS


def nome(o):
    return MARCAS[_plat(o)]["nome"]


def texto_oficial(o):
    return f"Loja oficial {nome(o)}"


def hoje_por_marca(fila, campo, hoje):
    """Quantas ofertas de cada marca já saíram no dia `hoje` ("AAAA-MM-DD") no canal do `campo`
    ("postado_em" = Instagram, "telegram_em" = Telegram)."""
    cont = {}
    for o in fila["ofertas"].values():
        if eh_marca(o) and str(o.get(campo) or "").startswith(hoje):
            cont[o["plataforma"]] = cont.get(o["plataforma"], 0) + 1
    return cont
