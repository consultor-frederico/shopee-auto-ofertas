"""Marcas oficiais que entram pela Awin (src/awin.py). Cada marca é uma "plataforma" própria na fila.

Para incluir uma marca nova: aprovar o programa na Awin, marcar o anunciante no feed (Ferramentas → Crie um Feed,
o mesmo feed das outras) e acrescentar uma linha aqui. O resto do robô (arte, legenda, Telegram, limites diários)
lê esta tabela.

- anunciante: pedaços do nome do anunciante na coluna merchant_name do feed (sem acento, minúsculas)
- prefixo: começo do id na fila ("sn123"), para não misturar com ids da Shopee
- conferir_site: o feed da marca demora a atualizar, então o preço é conferido na loja (VTEX) antes de postar
- comissao_pct: CPA do programa (sem a chave vale config.AWIN_COMISSAO_PCT)
- acessorios_celular: loja de acessórios de celular (regras próprias em awin.categoria_do_produto)
- logo / logo_fundo: logo oficial (o do perfil da marca na Awin, em assets/marcas/) e a cor de fundo dele; entra sem
  mudar cor nem proporção numa plaquinha na faixa "LOJA OFICIAL" da arte (src/lojas_arte.py)
"""

MARCAS = {
    "sharkninja": {"nome": "Shark Ninja", "loja": "Shark-Ninja BR", "cor": "#0B3C6F", "prefixo": "sn",
                   "anunciante": ("shark", "ninja"), "hashtag": "#sharkninja", "conferir_site": False,
                   "logo": "sharkninja.png", "logo_fundo": "#FFFFFF"},
    "arno": {"nome": "Arno", "loja": "Arno BR", "cor": "#C8102E", "prefixo": "ar",
             "anunciante": ("arno",), "hashtag": "#arno", "conferir_site": True,
             "logo": "arno.png", "logo_fundo": "#FFFFFF"},
    # aprovada em 26/10/2026, CPA 10%
    "vxcase": {"nome": "VX Case", "loja": "VX Case BR", "cor": "#111111", "prefixo": "vx",
               "anunciante": ("vx case", "vxcase"), "hashtag": "#vxcase", "conferir_site": False,
               "comissao_pct": 10.0, "acessorios_celular": True,
               "logo": "vxcase.png", "logo_fundo": "#000000"},
}


def comissao_pct(plataforma):
    from . import config
    return MARCAS.get(plataforma, {}).get("comissao_pct", config.AWIN_COMISSAO_PCT)


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
