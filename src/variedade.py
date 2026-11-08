"""Variedade: evita que o mesmo TIPO de produto apareça várias vezes seguidas.

Ex.: "Bomba de Ar Portátil", "Compressor de Ar 7 em 1" e "Inflador de Pneus" são nomes
diferentes (não caem no filtro de produto repetido), mas para quem segue a página é tudo
"bomba de encher". Aqui eles viram a mesma FAMÍLIA, e cada família tem limite:

- no garimpo: no máximo config.MAX_PENDENTES_POR_FAMILIA na fila ao mesmo tempo;
- na postagem (Instagram e Telegram): a mesma família só volta depois de
  config.HORAS_ENTRE_FAMILIA horas naquele canal.
"""
import re
from datetime import datetime, timedelta

from . import config, curadoria, marcas

# Palavras que, em qualquer ponto do nome, definem a família. A ordem importa:
# a primeira família que bater vence (ex.: "relógio smartwatch" → smartwatch).
FAMILIAS = {
    "bomba de ar": ["compressor", "inflador", "calibrador", "bomba de ar", "encher pneu", "bomba pneu"],
    "boneca reborn": ["reborn"],
    "interruptor inteligente": ["interruptor"],   # 27/10/2026: entraram dois iguais (um com a marca na frente)
    "umidificador": ["umidificador", "difusor de aroma", "difusor de ar", "aromatizador eletrico"],
    "travesseiro": ["travesseiro"],   # 27/10/2026: dois travesseiros cervicais na fila ao mesmo tempo
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
    # projetor antes de luminária: "Luminária Astronauta Projetor" e "Projetor Astronauta" são o mesmo achado
    "projetor": ["projetor", "luz noturna", "astronauta", "galaxia"],
    "luminaria": ["luminaria", "abajur", "fita led", "led rgb"],
    "espelho": ["espelho"],
    "arranhador": ["arranhador"],
    "fonte pet": ["fonte de agua", "bebedouro"],
    "cama pet": ["cama pet", "caminha", "cama suspensa"],
    "carrinho controle remoto": ["carrinho", "carro de controle", "carro controle remoto", "drift"],
    "robo brinquedo": ["robo", "transformers", "optimus"],
    "blocos de montar": ["blocos", "building", "lego"],
    "pelucia": ["pelucia"],
    "oculos": ["oculos"],
    "ferramenta eletrica": ["furadeira", "parafusadeira", "motosserra", "serra eletrica", "esmerilhadeira",
                            "maquina de solda", "lixadeira"],
    "acendedor": ["acendedor", "isqueiro"],
}


# Produtos "de vitrine": todo mundo posta, não são achado. A IA às vezes dá nota alta para eles,
# então aqui o teto é fixo — não passam de uau 6 e por isso não são postados.
COMUNS = {"smartwatch", "camera de seguranca", "fone de ouvido", "carregador", "caixa de som",
          "aspirador", "bomba de ar", "boneca reborn", "lanterna", "ventilador", "mop", "garrafa",
          "ferramenta eletrica", "acendedor"}
TETO_COMUM = 6


# Nome de franquia/personagem = risco de réplica. A IA deveria dar 0, mas às vezes deixa passar.
FRANQUIAS = ["transformers", "optimus", "bumblebee", "megatron", "marvel", "iron heroes", "homem aranha",
             "spider", "batman", "vingadores", "avengers", "disney", "stitch", "pokemon", "my little pony",
             "gabby", "hello kitty", "sanrio", "kuromi", "naruto", "dragon ball", "one piece", "harry potter",
             "hogwarts", "barbie", "frozen", "minecraft", "sonic", "mario", "star wars", "lego", "patrulha canina",
             "peppa", "bluey", "hot wheels", "capitao america", "hulk", "wandinha", "labubu", "paw patrol",
             "mickey", "minnie", "toy story", "carros mcqueen", "mcqueen", "galinha pintadinha",
             "mundo bita", "patati", "free fire", "fortnite", "roblox", "among us"]


# Marca de OUTRA empresa no produto (04/11/2026): o Instagram removeu o carrossel com o "Suporte MagSafe com
# Ventosa" da VX Case por "falsificação/propriedade intelectual" — produto original, mas "MagSafe" e o iPhone
# na legenda são da Apple. Produto original vendido com o nome da própria marca (fone JBL, barbeador Xiaomi do
# lançamento do Mercado Livre e dos "conhecidos") continua liberado; o que trava é:
#   - console retrô/emulador (Anbernic, R36S, "mil jogos"): pirataria aos olhos da Meta, sempre;
#   - Apple (MagSafe, iPhone, iPad, AirPods...): quase sempre é acessório de outra empresa;
#   - outra marca conhecida quando é acessório/compatível/"tipo" (capa Galaxy, copo tipo Stanley) ou quando a
#     loja oficial que vende é outra (VX Case vendendo capa Samsung);
#   - JBL/Stanley/Samsung/Nike/Adidas fora da loja oficial (exceto Mercado Livre): réplica comum.
EMULADOR = ["anbernic", "r36s", "game stick", "emulador", "console retro", "videogame retro", "jogos retro",
            "mil jogos"]
APPLE = ["magsafe", "iphone", "apple", "airpod", "airpods", "ipad", "macbook", "airtag", "imac"]
MARCAS_CONHECIDAS = {"samsung": ["samsung", "galaxy tab", "galaxy buds", "galaxy watch"],
                     "xiaomi": ["xiaomi", "redmi"], "motorola": ["motorola"], "jbl": ["jbl"],
                     "stanley": ["stanley"], "nike": ["nike"], "adidas": ["adidas"],
                     "sony": ["playstation", "ps5", "ps4"], "microsoft": ["xbox"], "nintendo": ["nintendo"],
                     "gopro": ["gopro"], "dyson": ["dyson"], "amazon": ["echo dot"]}
ACESSORIO = ["para", "pra", "serve", "compativel", "capa", "case", "pelicula", "suporte", "pulseira", "tipo", "estilo",
             "inspirado", "replica", "similar", "modelo"]
# muito falsificadas: na Shopee/AliExpress só passam se a loja for a oficial (Mercado Livre é catálogo da marca)
FALSIFICADAS = {"jbl", "stanley", "samsung", "nike", "adidas"}
_RE_GALAXY = re.compile(r" galaxy (?:[sazm]\d|z? ?flip|z? ?fold|note)")   # "projetor galaxy" é genérico


def _tem(txt, termos):
    return any(_texto(t) in txt for t in termos)


def marca_terceiro(o):
    if isinstance(o, str):
        o = {"nome": o}
    txt = _texto(" ".join(str(o.get(k) or "") for k in ("nome", "titulo", "gancho")))
    dono = _texto(" ".join(str(o.get(k) or "") for k in ("marca", "loja")))
    if _tem(txt, EMULADOR):
        return True
    if _tem(txt, APPLE) and " apple " not in dono:
        return True
    for marca, termos in MARCAS_CONHECIDAS.items():
        if not (_tem(txt, termos) or (marca == "samsung" and _RE_GALAXY.search(txt))):
            continue
        if _tem(dono, [marca] + termos):
            continue   # loja/marca é a própria (Samsung vendendo Samsung)
        if o.get("marca") or _tem(txt, ACESSORIO):
            return True   # loja oficial de outra marca, ou acessório "para"/"tipo" a marca
        if marca in FALSIFICADAS and o.get("plataforma") != "mercadolivre" and not _tem(dono, ["oficial", "official"]):
            return True   # "JBL" em loja qualquer da Shopee: grande chance de ser réplica
    return False


def franquia(o):
    """Franquia/personagem ou marca de outra empresa (zera o uau: fora de Instagram, Facebook, Telegram e kits)."""
    txt = _texto(o if isinstance(o, str) else o.get("nome", ""))
    if not isinstance(o, str) and marcas.eh_marca(o):   # o nome da própria marca (Lego) não conta como franquia
        txt = txt.replace(_texto(marcas.nome(o)), " ")
    return any(_texto(f) in txt for f in FRANQUIAS) or marca_terceiro(o)


# Utilidade comum (02/11/2026, reclamação dos seguidores: "varal, vaporizador, nada interessante").
# Trava fixa no código, vale também para marca: nunca passa de uau 5, aconteça o que a IA disser.
CASA_COMUM = ["varal", "pote", "potes", "porta mantimento", "organizador", "cabide", "prateleira", "espelho",
              "tapete", "cortina", "lixeira", "comoda", "mesa de cabeceira", "painel ripado", "ripado", "panela",
              "liquidificador", "batedeira", "cafeteira", "torradeira", "ventilador", "aquecedor", "vaporizador",
              "passadeira", "ferro de passar", "multiprocessador", "processador de alimentos", "aparelho de pressao",
              "monitor de pressao", "medidor de pressao", "balanca", "travesseiro", "almofada", "mop", "vassoura",
              "rodo", "escova sanitaria", "saboneteira", "toalha", "lencol", "edredom", "jogo de cama",
              "nescafe", "dolce gusto", "chaleira", "sanduicheira", "air fryer", "fritadeira", "garrafa termica"]
TETO_CASA_COMUM = 5


_RE_CASA = None


def casa_comum(o):
    """Aceita plural ("espelhos", "potes", "varais", "organizadores"): em 03/11/2026 "Kit 3 Espelhos" escapou."""
    global _RE_CASA
    if _RE_CASA is None:
        import re
        partes = []
        for p in CASA_COMUM:
            palavras = _texto(p).split()
            partes.append(r"\s".join(re.escape(w[:-1]) + r"(?:l|is|es|s)?" if w.endswith("l") else
                                     re.escape(w) + r"(?:s|es)?" for w in palavras))
        _RE_CASA = re.compile(r" (?:" + "|".join(partes) + r") ")
    txt = _texto(o if isinstance(o, str) else o.get("nome", ""))
    return bool(_RE_CASA.search(txt))


def uau(o):
    """Fator uau já com o teto dos produtos de vitrine (e zero para franquia/personagem)."""
    if franquia(o):
        return 0.0
    nota = float(o.get("uau", 0) or 0)
    if casa_comum(o):
        return min(nota, TETO_CASA_COMUM)
    if marcas.eh_marca(o):   # marca oficial (catálogo curado): aspirador/air fryer não são "vitrine"
        return nota
    if o.get("lancamento_ml"):   # lançamento do Mercado Livre (até config.ML_LANCAMENTO_ATE): conhecido pode entrar
        return nota
    return min(nota, TETO_COMUM) if familia(o) in COMUNS else nota


def diferenciado(o, minimo=None):
    return uau(o) >= (config.UAU_MINIMO_POSTAR if minimo is None else minimo)


def para_instagram(o):
    """Carrossel/feed: uau mais alto que o do Telegram e foto aprovada (quando o Gemini olhou)."""
    if "gancho" not in o:   # nota dada pela regra antiga (antes de 02/11/2026): não vai mais para o Instagram
        return False
    if o.get("foto_nota") is not None and o["foto_nota"] < config.FOTO_MINIMA:
        return False
    return diferenciado(o, config.UAU_MINIMO_INSTAGRAM)


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
        if o.get("status") == "pendente" and "gancho" in o:   # regra antiga não ocupa vaga
            f = familia(o)
            cont[f] = cont.get(f, 0) + 1
    return cont
