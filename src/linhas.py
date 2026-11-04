"""🗂️ Linhas temáticas do Garimpo VIP (04/11/2026, itens 1 e 3 aprovados pelo Fred: "os produtos estão muito misturados").

1) Dia temático — cada dia da semana tem a sua linha, nos carrosséis do Instagram e no canal do Telegram:
   seg CASA · ter BELEZA · qua TECH · qui COZINHA · sex FERRAMENTAS E CARRO · sáb PET E BEBÊ · dom MAIS VENDIDOS.
   Vale para todas as lojas (Shopee, AliExpress, marcas da Awin e Mercado Livre quando ligar).
   O carrossel pega primeiro os produtos da linha do dia; se não fechar o mínimo, completa com outras linhas
   (cada produto continua com a faixa da linha dele). Domingo pega os mais vendidos garimpados na semana.
   O garimpo reserva parte das buscas para a linha do dia (a rodada das 17:45 já busca para o dia seguinte).
2) Faixa de cor + nome da linha na arte ("LINHA CASA"), por dentro da moldura de Natal.

Não mexe em: Kits do Zé (qua/sáb 18:45, têm tema próprio), Kits de Natal (20h), brincadeiras de seg/qui (usam os
produtos do dia), curadoria (uau>=8) nem na Ana (só Garimpo VIP).

Liga com LINHAS=1 (dia temático + faixa) — ou só a faixa com LINHAS_FAIXA=1. LINHA_HOJE=tech força a linha (teste).
Prévia: python -m src.linhas previa  → data/relatorios/linhas/
"""
import os
import re
import unicodedata
from datetime import timedelta

from PIL import Image, ImageDraw

from . import config

L, A = 1080, 1350

# chave: nome na arte, cor da faixa, categoria do robô usada nas buscas extras, palavras que identificam a linha
LINHAS = {
    "casa": {"nome": "CASA", "cor": (47, 107, 94), "cat": "lar"},
    "cozinha": {"nome": "COZINHA", "cor": (190, 78, 40), "cat": "lar"},
    "beleza": {"nome": "BELEZA", "cor": (176, 58, 104), "cat": "beleza"},
    "tech": {"nome": "TECH", "cor": (40, 76, 150), "cat": "eletronicos"},
    "ferramentas": {"nome": "FERRAMENTAS", "cor": (176, 112, 20), "cat": "masculino"},
    "carro": {"nome": "CARRO", "cor": (58, 64, 74), "cat": "automotivo"},
    "pet": {"nome": "PET", "cor": (96, 130, 40), "cat": "pet"},
    "bebe": {"nome": "BEBÊ E CRIANÇA", "cor": (112, 88, 176), "cat": "brinquedos"},
    "achados": {"nome": "ACHADOS", "cor": (122, 92, 34), "cat": None},   # não encaixou em nenhuma
}
MAIS_VENDIDOS = "mais_vendidos"
# weekday() → linhas do dia (0 = segunda)
DIAS = {0: ["casa"], 1: ["beleza"], 2: ["tech"], 3: ["cozinha"], 4: ["ferramentas", "carro"],
        5: ["pet", "bebe"], 6: [MAIS_VENDIDOS]}
NOME_DIA = {0: "segunda", 1: "terça", 2: "quarta", 3: "quinta", 4: "sexta", 5: "sábado", 6: "domingo"}
TITULO_DIA = {0: "Dia da Casa", 1: "Dia da Beleza", 2: "Dia do Tech", 3: "Dia da Cozinha",
              4: "Dia das Ferramentas e do Carro", 5: "Dia do Pet e do Bebê", 6: "dia dos Mais Vendidos"}
EMOJI_DIA = {0: "🏠", 1: "💄", 2: "🔌", 3: "🍳", 4: "🛠️🚗", 5: "🐾🍼", 6: "🏆"}

# Palavras que puxam o produto para a linha (procuradas no nome + título + termo de busca, sem acento).
# A ordem importa: a 1ª linha que achar palavra leva o produto (ex.: "aspirador automotivo" é CARRO, não CASA).
PALAVRAS = [
    ("achados", r"baralho|\btaro\b|tarot|cigano"),
    ("tech", r"smartwatch|relogio inteligente|smart ?band|bluetooth|oculos inteligente|impressora|fone de ouvido|ring light|anel de luz"),
    ("bebe", r"baba eletronica|\bbebes?\b|infantil|crianca|\bkids\b|montessori|maternidade|fralda|mamadeira|"
             r"chupeta|mordedor|\bberco"),
    ("pet", r"\bpets?\b|cachorr|\bc[aã]o\b|\bcaes\b|gato|felin|canin|areia sanitaria|caixa de areia|coleira|peitoral|"
            r"arranhador|comedouro|bebedouro|aquario|passaro|\baves?\b|\bracao|hamster|focinh"),
    ("bebe", r"\bmenin[oa]|brinquedo|squishy|fidget|anti.?stress|boneca|boneco|montessori|educativ|"
             r"controle remoto|\brc\b|blocos|lego|quebra.?cabeca|massinha|slime|pelucia|chupeta|"
             r"dinossauro|hot wheels|"
             r"tabuleiro|lousa magica|pista|atividades|tapete de atividade"),
    ("carro", r"automotiv|veicular|\bcarro|\bauto\b|porta.?malas|farol|retrovisor|volante|\bpneu|\bmoto\b|"
              r"capacete|banco do carro|para.?brisa|estepe|calibrador|cambio|placa de carro|dash ?cam"),
    ("cozinha", r"cozinha|panela|frigideira|air ?fryer|fritadeira|liquidific|batedeira|mixer|processador|"
                r"cafeteira|\bcafe\b|chaleira|sanduicheira|grill|torradeira|forno|fogao|cooktop|talher|faca|"
                r"tabua|\bpotes?\b|hermetic|tempero|escorredor|\bpia\b|louca|descascador|picador|ralador|cortador de|"
                r"mini seladora|seladora|garrafa termica|marmita|lancheira|copo|caneca|jarra|geladeira|"
                r"utensilio|espatula|concha|assadeira|formas? de (?:bolo|gelo|silicone)|forminha|bowl|tigela|sobremesa|pipoca|sorvete|churrasc|espeto|abridor|moedor|"
                r"balanca de cozinha|dispenser de agua|filtro de agua"),
    ("ferramentas", r"ferrament|furadeira|parafusadeira|chave de fenda|chave inglesa|alicate|martelo|trena|"
                    r"nivel a laser|\bserra\b|esmerilhadeira|lixadeira|soprador|compressor|lanterna|multimetro|"
                    r"solda|kit reparo|maleta de|torquimetro|parafuso|broca|tatica|canivete|lavadora de alta|"
                    r"\bwap\b|jardinagem|mangueira|pulverizador|cortador de grama|escada"),
    ("beleza", r"maquiagem|make|batom|\blip\b|sombra|pincel|skincare|skin care|serum|hidratante|facial|"
               r"cabelo|chapinha|prancha|secador|escova secadora|escova alisadora|modelador|babyliss|cachos|"
               r"unha|manicure|esmalte|perfume|barb|barba|aparador|depilador|cilios|curvex|espelho de maquiagem|"
               r"massageador|spa\b|autocuidado|cosmetic|creme|protetor solar|bolsa|brinco|\bcolar\b|\banel\b|pulseira|"
               r"relogio(?! inteligente)|oculos|carteira|joia|bijuteria|necessaire|touca de cetim|fronha de cetim|presilha|"
               r"organizador de maquiagem|porta joias|tenis|sandalia|vestido|bone\b|mochila"),
    ("tech", r"bluetooth|fone|headset|smartwatch|relogio inteligente|smart|wifi|wi-fi|usb|carregador|"
             r"power ?bank|bateria portatil|mouse|teclado|notebook|tablet|celular|smartphone|camera|webcam|"
             r"projetor|caixa de som|speaker|microfone|ring light|tripe|tripod|gimbal|console|video ?game|"
             r"controle|gamer|monitor|\btv\b|hdmi|roteador|impressora|tomada inteligente|lampada inteligente|"
             r"alexa|drone|gadget|led rgb|eletronic|cabo|adaptador|ssd|pendrive|cartao de memoria|tuya"),
    ("casa", r"organizador|luminaria|lampada|\bled\b|fita led|tapete|cortina|almofada|cobertor|edredom|lencol|"
             r"travesseiro|toalha|banheiro|chuveiro|box\b|varal|cabide|guarda.?roupa|closet|prateleira|"
             r"nicho|painel|rack|estante|decora|quadro|vaso|planta|espelho|umidificador|difusor|aromatiz|vela|"
             r"aspirador|mop|vassoura|rodo|limpeza|limpador|lixeira|dispenser|ventilador|aquecedor|"
             r"cama|colchao|sofa|cadeira|mesa\b|porta.?retrato|relogio de parede|campainha|fechadura"),
]
_PALAVRAS = [(lin, re.compile(rx)) for lin, rx in PALAVRAS]
# se nenhuma palavra bater: a categoria do robô decide
POR_CATEGORIA = {"lar": "casa", "casa_fofa": "casa", "eletronicos": "tech", "automotivo": "carro", "pet": "pet",
                 "brinquedos": "bebe", "beleza": "beleza", "cabelo": "beleza", "moda": "beleza",
                 "autocuidado": "beleza", "feminino": "beleza", "masculino": "beleza"}

# Buscas extras do garimpo para cada linha (somadas às palavras fixas do nicho): (categoria do robô, termo)
BUSCAS = {
    "casa": ["organizador guarda roupa", "luminária sensor de presença", "fita led", "tapete banheiro",
             "umidificador", "organizador multifuncional", "aspirador portátil", "luminária decorativa",
             "cortina blackout", "prateleira adesiva", "cabideiro de chão", "difusor de aromas",
             "kit organizador closet", "luminária nuvem"],
    "cozinha": ["organizador cozinha", "utensílios cozinha", "air fryer acessórios", "jogo de panelas",
                "potes herméticos", "porta tempero giratório", "mini processador elétrico", "cortador multifuncional",
                "mini seladora", "garrafa térmica inteligente", "tábua de corte", "escorredor de louça",
                "mixer portátil", "organizador de geladeira", "kit churrasco", "panela elétrica"],
    "beleza": ["kit maquiagem", "skincare", "escova secadora", "massageador facial", "espelho led",
               "kit pincel maquiagem", "modelador de cachos", "cabine led unha", "máquina de barbear",
               "aparador de pelos", "kit barba", "organizador de maquiagem", "curvex aquecido", "kit manicure"],
    "tech": ["fone bluetooth", "smartwatch", "caixa de som bluetooth", "power bank", "mini projetor portátil",
             "carregador turbo", "câmera wifi", "tomada inteligente", "lâmpada inteligente", "ring light",
             "mini impressora térmica", "teclado sem fio", "gadget criativo", "suporte celular"],
    "ferramentas": ["kit ferramentas multifuncional", "parafusadeira", "furadeira sem fio", "lanterna tática",
                    "trena laser", "nível a laser", "alicate multifuncional", "kit chave catraca",
                    "soprador térmico", "multímetro digital", "maleta de ferramentas", "lavadora de alta pressão"],
    "carro": ["aspirador automotivo", "suporte veicular celular", "câmera de ré", "organizador porta malas",
              "carregador veicular", "compressor de ar portátil", "kit limpeza automotiva", "luz ambiente carro",
              "suporte magnético carro", "capa banco carro", "gadget carro", "organizador banco carro"],
    "pet": ["comedouro automático", "bebedouro fonte pet", "arranhador gato", "caminha pet",
            "brinquedo interativo gato", "escova pet removedor pelos", "comedouro lento", "coleira peitoral",
            "luva removedora de pelos", "bebedouro portátil pet", "brinquedo para cachorro"],
    "bebe": ["brinquedo montessori", "brinquedo educativo", "blocos de montar", "babá eletrônica",
             "kit higiene bebê", "mordedor bebê", "tapete de atividades bebê", "luminária infantil",
             "quebra cabeça infantil", "projetor estrelas", "lousa mágica", "organizador de fraldas"],
}
BUSCAS_POR_GARIMPO = int(os.getenv("LINHAS_BUSCAS", "8"))   # das 24 buscas da rodada, quantas vão para a linha do dia
NA_FILA_POR_GARIMPO = int(os.getenv("LINHAS_NA_FILA", "8"))  # das 15 vagas da fila por rodada, quantas a linha pega primeiro
JANELA_MAIS_VENDIDOS = 7   # domingo: mais vendidos entre os garimpados nos últimos 7 dias


def ligado():
    return config.PERFIL != "ana" and os.getenv("LINHAS", "0") == "1"


def faixa_ligada():
    return config.PERFIL != "ana" and (ligado() or os.getenv("LINHAS_FAIXA", "0") == "1")


def _sem_acento(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def de(oferta):
    """Linha do produto (chave de LINHAS)."""
    if oferta.get("linha") in LINHAS:
        return oferta["linha"]
    texto = _sem_acento(" ".join(str(oferta.get(k) or "") for k in ("titulo", "nome")))
    for lin, rx in _PALAVRAS:
        if rx.search(texto):
            return lin
    termo = _sem_acento(oferta.get("palavra"))
    for lin, rx in _PALAVRAS:
        if termo and rx.search(termo):
            return lin
    return POR_CATEGORIA.get(oferta.get("categoria"), "achados")


def marcar(oferta):
    """Guarda a linha na oferta (a arte e a vitrine leem daqui)."""
    oferta["linha"] = de(oferta)
    return oferta["linha"]


def _dia(hoje=None):
    from .garimpar import agora
    return (hoje or agora()).weekday()


def do_dia(hoje=None):
    """Linhas do dia (lista de chaves; domingo = ['mais_vendidos']). LINHA_HOJE força (teste)."""
    forcada = (os.getenv("LINHA_HOJE") or "").strip().lower()
    if forcada in LINHAS or forcada == MAIS_VENDIDOS:
        return [forcada]
    return DIAS[_dia(hoje)]


def para_garimpo(hoje=None):
    """Linhas que o garimpo deve reforçar: de manhã/meio-dia a de hoje; a rodada da tarde (>=15h) já busca a de amanhã.
    Domingo (mais vendidos) não precisa de busca própria."""
    from .garimpar import agora
    t = hoje or agora()
    if t.hour >= 15:
        t = t + timedelta(days=1)
    return [lin for lin in do_dia(t) if lin in BUSCAS]


def termos_extra(n=None):
    """[(categoria, termo)] para o garimpo da rodada, em rodízio entre as linhas do dia. Só categorias do nicho."""
    import random
    if not ligado():
        return []
    n = BUSCAS_POR_GARIMPO if n is None else n
    filas = {lin: random.sample(BUSCAS[lin], len(BUSCAS[lin])) for lin in para_garimpo()}
    saida = []
    while len(saida) < n and any(filas.values()):
        for lin, termos in filas.items():
            cat = LINHAS[lin]["cat"]
            if termos and len(saida) < n and cat in config.NICHO:
                saida.append((cat, termos.pop()))
    return saida


def ordenar(ofertas, hoje=None):
    """Põe na frente as ofertas da linha do dia (mantendo a ordem de pontos entre elas). Domingo: mais vendidos
    garimpados nos últimos 7 dias primeiro. Sem o dia temático ligado, devolve como veio."""
    if not ligado():
        return list(ofertas)
    linhas = do_dia(hoje)
    if linhas == [MAIS_VENDIDOS]:
        from datetime import datetime
        from .garimpar import BRT, FMT, agora
        limite = (hoje or agora()) - timedelta(days=JANELA_MAIS_VENDIDOS)

        def recente(o):
            try:
                return datetime.strptime(o["criado_em"], FMT).replace(tzinfo=BRT) >= limite
            except Exception:
                return False
        semana = sorted((o for o in ofertas if recente(o)), key=lambda o: o.get("vendas") or 0, reverse=True)
        return semana + [o for o in ofertas if o not in semana]
    return [o for o in ofertas if de(o) in linhas] + [o for o in ofertas if de(o) not in linhas]


def eh_do_dia(oferta, hoje=None):
    linhas = do_dia(hoje)
    return linhas == [MAIS_VENDIDOS] or de(oferta) in linhas


# ---------------------------------------------------------------- legenda
def abertura_legenda(hoje=None):
    """1ª frase da legenda do carrossel no dia temático ('🍳 Quinta é Dia da Cozinha no Garimpo!')."""
    if not ligado():
        return ""
    d = _dia(hoje)
    forcada = (os.getenv("LINHA_HOJE") or "").strip().lower()
    if forcada:
        dia_forcado = next((k for k, v in DIAS.items() if forcada in v), None)
        d = d if dia_forcado is None else dia_forcado
    return f"{EMOJI_DIA[d]} {NOME_DIA[d].capitalize()} é {TITULO_DIA[d]} no Garimpo!"


# ---------------------------------------------------------------- arte
def _fonte(tam, peso="Black"):
    from . import imagem
    return imagem._fonte(tam, peso)


def faixa(img, oferta):
    """Arte 1080x1350 dentro da faixa da linha: tarja colorida no topo com "LINHA CASA" e borda fina da mesma cor.
    Vai por dentro da moldura de Natal (o Natal fica por fora de tudo). Fora do formato do feed, volta como veio."""
    if not faixa_ligada() or img.size != (L, A):
        return img
    try:
        info = LINHAS[de(oferta)]
        cor = info["cor"]
        topo, borda = 78, 14
        esc = min((L - 2 * borda) / L, (A - topo - borda) / A)
        w, h = int(L * esc), int(A * esc)
        novo = Image.new("RGB", (L, A), cor)
        x0, y0 = (L - w) // 2, topo
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 18, fill=255)
        novo.paste(img.convert("RGB").resize((w, h), Image.LANCZOS), (x0, y0), m)
        d = ImageDraw.Draw(novo)
        f1, f2 = _fonte(30, "SemiBold"), _fonte(46, "Black")
        t1, t2 = "LINHA", info["nome"]
        gap = 14
        tw = d.textlength(t1, font=f1) + gap + d.textlength(t2, font=f2)
        x = (L - tw) / 2
        cy = topo / 2 + 2
        d.text((x, cy), t1, font=f1, fill=(255, 255, 255, 220), anchor="lm")
        x += d.textlength(t1, font=f1) + gap
        d.text((x, cy), t2, font=f2, fill=(255, 255, 255), anchor="lm")
        # tracinhos dos lados, para a tarja ler como "faixa" de coleção
        for xa, xb in ((60, (L - tw) / 2 - 26), ((L + tw) / 2 + 26, L - 60)):
            if xb - xa > 20:
                d.line([(xa, cy), (xb, cy)], fill=tuple(min(255, c + 70) for c in cor), width=4)
        return novo
    except Exception as e:
        print(f"::warning::Faixa da linha não saiu ({e}); fica a arte sem faixa.")
        return img


# ---------------------------------------------------------------- prévia
def previa(pasta=None):
    """Gera, sem postar: 1 slide de cada linha (produtos de verdade da fila, nos 3 estilos do carrossel), a grade com
    todos, uma capa, um post do Telegram e quantos produtos a fila tem de cada linha. Pasta padrão:
    data/relatorios/linhas/."""
    import collections
    import shutil
    from . import achados_artes as artes, imagem
    from .garimpar import carregar_fila
    os.environ.setdefault("LINHAS_FAIXA", "1")
    pasta = config.RAIZ / (pasta or "data/relatorios/linhas")
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True, exist_ok=True)
    fila = carregar_fila()
    pend = [o for o in fila["ofertas"].values() if o.get("status") == "pendente" and o.get("titulo")]
    todas = [o for o in fila["ofertas"].values() if o.get("titulo") and o.get("imagem")]
    cont = collections.Counter(de(o) for o in pend)
    print("Fila pendente por linha:", dict(cont))
    feitos, usados = [], {}
    for i, lin in enumerate(l for l in LINHAS if l != "achados"):
        cands = [o for o in todas if de(o) == lin and o.get("nivel") in ("ouro", "achado")]
        cands.sort(key=lambda o: (o.get("status") == "pendente", o.get("uau") or 0), reverse=True)
        for o in cands[:8]:
            try:
                foto = imagem._baixar_foto(o["imagem"])
            except Exception:
                continue
            arq = pasta / f"{i + 1}-{lin}.jpg"
            artes.produto_garimpo(i % artes.N_PRODUTO, o, foto, 1 + i % 4, arq)
            print(f"🖼️  {LINHAS[lin]['nome']}: {o['titulo']}")
            feitos.append(arq)
            usados[lin] = (o, foto)
            break
    if "tech" in usados:
        artes.capa_produto(usados["tech"][0], usados["tech"][1], 3, "joia", pasta / "capa-do-carrossel.jpg")
    if "cozinha" in usados:
        imagem.gerar(usados["cozinha"][0], pasta / "post-do-telegram.jpg", foto=usados["cozinha"][1])
    if feitos:
        g = Image.new("RGB", (4 * 540, 2 * 675), (255, 255, 255))
        for k, arq in enumerate(feitos[:8]):
            g.paste(Image.open(arq).resize((540, 675), Image.LANCZOS), ((k % 4) * 540, (k // 4) * 675))
        g.save(pasta / "0-todas-as-linhas.jpg", quality=88)
    (pasta / "fila-por-linha.txt").write_text(
        "Produtos esperando na fila hoje, por linha:\n" +
        "\n".join(f"{LINHAS[k]['nome']}: {v}" for k, v in cont.most_common()), encoding="utf-8")
    print(f"🏁 {len(feitos)} prévias em {pasta}")


if __name__ == "__main__":
    import sys
    if (sys.argv[1:] or [""])[0] == "previa":
        previa(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print("Uso: python -m src.linhas previa")
