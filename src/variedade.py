"""Variedade: evita que o mesmo TIPO de produto apareça várias vezes seguidas.

Ex.: "Bomba de Ar Portátil", "Compressor de Ar 7 em 1" e "Inflador de Pneus" são nomes
diferentes (não caem no filtro de produto repetido), mas para quem segue a página é tudo
"bomba de encher". Aqui eles viram a mesma FAMÍLIA, e cada família tem limite:

- no garimpo: no máximo config.MAX_PENDENTES_POR_FAMILIA na fila ao mesmo tempo;
- na postagem (Instagram e Telegram): a mesma família só volta depois de
  config.HORAS_ENTRE_FAMILIA horas naquele canal.
"""
from datetime import datetime, timedelta

from . import config, curadoria

# Palavras que, em qualquer ponto do nome, definem a família. A ordem importa:
# a primeira família que bater vence (ex.: "relógio smartwatch" → smartwatch).
FAMILIAS = {
    "bomba de ar": ["compressor", "inflador", "calibrador", "bomba de ar", "encher pneu", "bomba pneu"],
    "boneca reborn": ["reborn"],
    "smartwatch": ["smartwatch", "smart watch", "relogio inteligente", "smartband", "pulseira inteligente"],
    "camera de seguranca": ["camera ip", "camera de seguranca", "camera seguranca", "camera wifi",
                             "camera externa", "camera lampada", "camera ptz", "camera 4g"],
    "fone de ouvido": ["fone", "headset", "earbuds", "airpods", "tws"],
    "caixa de som": ["caixa de som", "caixa som", "partybox", "speaker"],
    "aspirador": ["aspirador"],
    "robo aspirador": ["robo aspirador"],
    "lanterna": ["lanterna"],
    "ventilador": ["ventilador"],
    "impressora": ["impressora"],
    "carregador": ["carregador", "power bank", "powerbank", "estacao de carregamento"],
    "mop": ["mop", "esfregao"],
    "garrafa": ["garrafa", "copo termico", "squeeze"],
    "luminaria": ["luminaria", "abajur", "fita led", "led rgb"],
    "espelho": ["espelho"],
    "arranhador": ["arranhador"],
    "fonte pet": ["fonte de agua", "bebedouro"],
    "cama pet": ["cama pet", "caminha", "cama suspensa"],
    "carrinho controle remoto": ["carrinho", "carro de controle", "carro controle remoto", "drift"],
    "projetor": ["projetor", "luz noturna"],
    "robo brinquedo": ["robo", "transformers", "optimus"],
    "blocos de montar": ["blocos", "building", "lego"],
    "pelucia": ["pelucia"],
    "oculos": ["oculos"],
    "ferramenta eletrica": ["furadeira", "parafusadeira", "motosserra", "serra eletrica", "esmerilhadeira",
                            "maquina de solda", "lixadeira"],
    "acendedor": ["acendedor", "isqueiro"],
}


def _texto(nome):
    return " " + " ".join(curadoria._norm(nome)) + " "


def familia(oferta_ou_nome):
    """Nome da família do produto (ex.: "bomba de ar"). Sem regra, usa a 1ª palavra significativa."""
    nome = oferta_ou_nome if isinstance(oferta_ou_nome, str) else oferta_ou_nome.get("nome", "")
    txt = _texto(nome)
    # "robo aspirador" precisa vencer "aspirador" e "robo"
    if " robo aspirador " in txt or (" aspirador " in txt and " robo " in txt):
        return "robo aspirador"
    for fam, termos in FAMILIAS.items():
        if any(_texto(t) in txt for t in termos):   # termos passam pela mesma limpeza do nome
            return fam
    from .garimpar import tipo_produto   # import tardio (garimpar importa este módulo)
    return tipo_produto(nome)


def _quando(o, campo):
    from .garimpar import BRT, FMT
    try:
        return datetime.strptime(o.get(campo) or "", FMT).replace(tzinfo=BRT)
    except ValueError:
        return None


def familias_recentes(fila, campo, horas=None):
    """Famílias que saíram nas últimas `horas` no canal (campo = "postado_em" ou "telegram_em")."""
    from .garimpar import agora
    limite = agora() - timedelta(hours=horas or config.HORAS_ENTRE_FAMILIA)
    fams = set()
    for o in fila["ofertas"].values():
        q = _quando(o, campo)
        if q and q >= limite:
            fams.add(familia(o))
    return fams


def ordenar(lista, recentes):
    """Mantém a ordem, mas joga para o fim quem é de família que saiu há pouco
    e, entre os demais, não deixa duas da mesma família em sequência."""
    novas, vistas, adiadas = [], set(), []
    for o in lista:
        f = familia(o)
        if f in recentes or f in vistas:
            adiadas.append(o)
        else:
            novas.append(o)
            vistas.add(f)
    return novas + adiadas


def contar_pendentes(fila):
    cont = {}
    for o in fila["ofertas"].values():
        if o.get("status") == "pendente":
            f = familia(o)
            cont[f] = cont.get(f, 0) + 1
    return cont
