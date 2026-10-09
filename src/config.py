"""Configurações do Garimpo VIP. Ajuste aqui o nicho, os filtros e o ritmo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
FONTE = RAIZ / "assets" / "Montserrat.ttf"

# --- Credenciais (segredos do GitHub) ---
SHOPEE_APP_ID = (os.getenv("SHOPEE_APP_ID") or "").strip()
SHOPEE_APP_SECRET = (os.getenv("SHOPEE_APP_SECRET") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
GROQ_URL = "https://api.groq.com/openai/v1"
# Ordem de preferência; se nenhum existir mais, o robô escolhe sozinho um modelo disponível.
# (a Groq desligou os modelos Llama em out/2026 — agora o principal é o gpt-oss-120b)
GROQ_MODELOS = [m.strip() for m in os.getenv(
    "GROQ_MODELOS", "openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.8-27b,llama-3.3-70b-versatile").split(",") if m.strip()]

# --- Nicho: palavras-chave buscadas na Shopee, por categoria ---
NICHO_GARIMPO = {
    "eletronicos": [
        "fone bluetooth", "smartwatch", "caixa de som bluetooth", "carregador turbo",
        "power bank", "mouse sem fio", "teclado sem fio", "suporte celular",
        "lâmpada inteligente", "câmera wifi", "fone tws", "ring light",
        "mini projetor portátil", "gadget criativo", "luminária lua", "mini impressora térmica",
        "tomada inteligente", "mini ventilador portátil",
    ],
    "lar": [
        "organizador cozinha", "luminária led", "air fryer acessórios", "jogo de panelas",
        "organizador guarda roupa", "mop giratório", "fita led", "potes herméticos",
        "umidificador", "aspirador portátil", "utensílios cozinha", "tapete banheiro",
        "utilidades domésticas criativas", "organizador multifuncional", "cortador multifuncional",
        "dispenser automático", "luminária sensor de presença", "mini seladora",
    ],
    "brinquedos": [
        "brinquedo educativo", "blocos de montar", "carrinho controle remoto",
        "boneca", "quebra cabeça infantil", "massinha de modelar", "pista hot wheels",
        "brinquedo montessori", "kit slime", "jogo de tabuleiro",
        "brinquedo criativo", "projetor estrelas", "lousa mágica", "robô brinquedo",
    ],
    "pet": [
        "caminha pet", "comedouro automático", "brinquedo para cachorro", "tapete higiênico",
        "arranhador gato", "bebedouro fonte pet", "coleira peitoral", "escova pet removedor pelos",
        "caixa de transporte pet", "roupa para cachorro",
        "brinquedo interativo gato", "comedouro lento", "bebedouro portátil pet", "luva removedora de pelos",
    ],
    "automotivo": [
        "aspirador automotivo", "suporte veicular celular", "câmera de ré", "organizador porta malas",
        "carregador veicular", "capa banco carro", "compressor de ar portátil", "kit limpeza automotiva",
        "lâmpada led farol", "tapete automotivo",
        "gadget carro", "organizador banco carro", "luz ambiente carro", "suporte magnético carro",
    ],
    "masculino": [
        "máquina de barbear", "carteira masculina", "relógio masculino", "kit barba",
        "aparador de pelos", "mochila masculina", "boné masculino", "perfume masculino",
        "camiseta masculina", "tênis masculino",
        "gadget masculino", "carteira inteligente", "kit ferramentas multifuncional", "lanterna tática",
    ],
}

# --- Filtros de qualidade (recalibrados em 09/10/2026 com 21.858 produtos dos dois perfis) ---
# Ouro: vai para o Instagram. Prata: completa o Instagram e vai para o Telegram. Abaixo: descartado.
# O que mais segura o Ouro é o "fator uau" (mantido em 7); vendas e comissão do Ouro foram
# afrouxadas (1000→500 vendas, R$8/10%→R$6/8%), o que ~triplica as ofertas Ouro sem perder qualidade.
NIVEIS = {
    "ouro": {"vendas": 500, "comissao_rs": 6.0, "comissao_pct": 8.0, "uau": 7},
    "prata": {"vendas": 500, "comissao_rs": 5.0, "comissao_pct": 8.0, "uau": 6},
}
COMISSAO_PCT_ALIEXPRESS = 7.0  # AliExpress paga 7% padrão; o corte em R$ (5 prata / 6 ouro) segue igual
# 💎 Achado escondido: produto excelente e muito diferente que ainda não viralizou (poucas vendas).
# Pouca prova social → só entra com nota alta e uau altíssimo, e no máximo ACHADOS_POR_DIA no Instagram.
NIVEL_ACHADO = {"vendas_min": 50, "nota": 4.8, "uau": 8, "comissao_rs": 3.0, "comissao_pct": 8.0}  # R$3 liberado pelo Fred em 09/10/2026
ACHADOS_POR_DIA = int(os.getenv("ACHADOS_POR_DIA", "1"))
NOTA_MINIMA = float(os.getenv("NOTA_MINIMA", "4.7"))
PRECO_MAXIMO = float(os.getenv("PRECO_MAXIMO", "300"))
UAU_SEM_IA = 6                 # nota padrão se a IA de curadoria estiver fora do ar
SIMILARIDADE_MAX = 0.55        # nomes mais parecidos que isso contam como o mesmo produto
# Palavras que barram o produto (fora do nicho ou arriscadas para anunciar)
PALAVRAS_PROIBIDAS = [
    "réplica", "replica", "vape", "cigarro", "arma", "faca tática", "sex", "erótic",
    "lingerie", "remédio", "emagrecedor", "suplemento",
]

# --- Ritmo ---
OFERTAS_POR_GARIMPO = int(os.getenv("OFERTAS_POR_GARIMPO", "15"))
PALAVRAS_POR_GARIMPO = int(os.getenv("PALAVRAS_POR_GARIMPO", "24"))   # total de buscas por rodada
# Garimpo profundo: parte das buscas é inventada pela IA a cada rodada (termos específicos e curiosos)
# e parte vem da memória (termos que já trouxeram Ouro/Achado). O resto são as palavras fixas do nicho.
PALAVRAS_IA_POR_GARIMPO = int(os.getenv("PALAVRAS_IA_POR_GARIMPO", "10"))
PALAVRAS_MEMORIA_POR_GARIMPO = int(os.getenv("PALAVRAS_MEMORIA_POR_GARIMPO", "4"))
# Páginas da Shopee por busca (página, ordem): 1 relevância, 2 mais vendidos, 5 maior comissão.
# As páginas 3–4 dos mais vendidos e a ordem "relevância" mostram o que fica escondido do topo.
# "ams" = só ofertas em que o vendedor paga comissão extra (20–40%): barato e diferente passa no filtro.
PAGINAS_FIXAS = ((1, 2), (2, 2), (3, 2), (4, 2), (1, 1), (1, 5), (1, 2, "ams"))
PAGINAS_PROFUNDAS = ((1, 2), (2, 2), (3, 2), (1, 1), (2, 1), (1, 5), (1, 2, "ams"), (2, 2, "ams"))
# Além das palavras: cavar nas lojas que já deram achado e garimpar direto por categoria da Shopee
LOJAS_POR_GARIMPO = int(os.getenv("LOJAS_POR_GARIMPO", "4"))
CATEGORIAS_POR_GARIMPO = int(os.getenv("CATEGORIAS_POR_GARIMPO", "4"))
PAGINAS_CATEGORIA = ((2, 2), (3, 2), (4, 2), (1, 1), (1, 2, "ams"), (2, 2, "ams"))
DIAS_SEM_REPETIR = 30          # Instagram: não repete o mesmo produto dentro desse prazo
DIAS_SEM_REPETIR_TELEGRAM = 14 # Telegram: campeão de vendas pode voltar depois disso
DIAS_APAGAR_POSTS = int(os.getenv("DIAS_APAGAR_POSTS", "15"))  # posts de oferta somem depois disso
DIAS_VALIDADE_PENDENTE = 3     # oferta não postada vence depois disso (preço muda)


# --- Ana Novo Achados (@ananovoachados): público feminino e LGBTQIA+ ---
NICHO_ANA = {
    "beleza": [
        "kit maquiagem", "skincare", "kit pincel maquiagem", "organizador de maquiagem",
        "massageador facial", "espelho led", "esponja maquiagem", "paleta de sombras",
        "lip tint", "rolo facial jade", "máscara facial led", "esmalte em gel kit",
        "cabine led unha", "curvex aquecido", "glitter corporal", "skincare coreano",
    ],
    "cabelo": [
        "escova secadora", "prancha alisadora", "escova alisadora", "modelador de cachos",
        "babyliss automático", "touca de cetim", "difusor cabelo cacheado", "kit acessórios cabelo",
        "presilha de cabelo", "secador de cabelo potente", "fronha de cetim", "escova desembaraçadora",
    ],
    "moda": [
        "bolsa feminina", "brinco feminino", "colar feminino", "relógio feminino",
        "vestido feminino", "sandália feminina", "organizador de joias", "óculos de sol estiloso",
        "bolsa transversal", "anel ajustável", "pochete estilosa", "kit pulseiras",
        "acessórios arco-íris", "camiseta oversized", "meia arco-íris", "brinco arco-íris",
    ],
    "autocuidado": [
        "massageador elétrico", "difusor de aromas", "pantufa fofinha", "kit spa em casa",
        "máscara para dormir", "garrafa motivacional", "massageador pescoço", "almofada de pescoço",
        "bolsa térmica", "kit manicure", "luminária sunset", "vela aromática",
    ],
    "casa_fofa": [
        "decoração quarto aesthetic", "luminária nuvem", "fita led quarto", "espelho decorativo",
        "luminária neon", "porta joias", "caneca criativa", "organizador acrílico",
        "projetor galáxia", "luminária arco-íris", "almofada fofa", "copo térmico stanley",
        "bandeira lgbt", "decoração arco-íris",
    ],
}

# --- Perfis (contas do Instagram). Escolha com a variável PERFIL (padrão: garimpo) ---
PERFIS = {
    "garimpo": {
        "nicho": NICHO_GARIMPO,
        "marca": "GARIMPO VIP",
        "nome": "Garimpo VIP",
        "arroba": "@garimpovip4",
        "hashtag": "#garimpovip",
        "pasta_dados": PASTA_DADOS,
        "logo": RAIZ / "assets" / "logo.png",
        "telegram": True,
        "tom": "Tom animado e direto, de quem garimpa as melhores ofertas.",
        "publico": "público geral que ama achadinhos",
        "cores": {"fundo": "#EEEDE9", "escuro": "#24150A", "destaque": "#A07E30",
                  "destaque_claro": "#E2BE68", "preco": "#24150A", "cinza": "#6E6458",
                  "sombra": "#DCD6CB"},
    },
    "ana": {
        "nicho": NICHO_ANA,
        "marca": "ANA NOVO ACHADOS",
        "nome": "Ana Novo Achados",
        "arroba": "@ananovoachados",
        "hashtag": "#ananovoachados",
        "pasta_dados": PASTA_DADOS / "ana",
        "logo": RAIZ / "assets" / "ana" / "logo.png",
        "telegram": False,
        "proibidas": ["infantil", "criança", "crianca", "bebê", "bebe", "menina", "menino", "kids"],
        "tom": ("Tom acolhedor, divertido e inclusivo, como uma amiga que indica achadinhos. "
                "Fale com mulheres e com o público LGBTQIA+ com carinho e sem estereótipos; "
                "prefira linguagem neutra no tratamento (\"você\", \"pra quem ama...\")."),
        "publico": "público feminino e LGBTQIA+ que ama beleza, moda, autocuidado e casa aesthetic",
        # cores do logo da Ana (a arte própria fica em src/layout_ana.py)
        "cores": {"fundo": "#12111F", "escuro": "#12111F", "destaque": "#7CDACA",
                  "destaque_claro": "#7CDACA", "preco": "#12111F", "cinza": "#9B99B5",
                  "sombra": "#1E1C36"},
    },
}

PERFIL = (os.getenv("PERFIL") or "garimpo").strip().lower()
if PERFIL not in PERFIS:
    raise SystemExit(f"PERFIL desconhecido: {PERFIL} (use: {', '.join(PERFIS)})")
_P = PERFIS[PERFIL]
NICHO = _P["nicho"]
MARCA, NOME_MARCA, ARROBA, HASHTAG_MARCA = _P["marca"], _P["nome"], _P["arroba"], _P["hashtag"]
LOGO = _P["logo"]
CORES = _P["cores"]
TOM, PUBLICO = _P["tom"], _P["publico"]
TELEGRAM_ATIVO = _P["telegram"]
PALAVRAS_PROIBIDAS = PALAVRAS_PROIBIDAS + _P.get("proibidas", [])
PASTA_PERFIL = _P["pasta_dados"]                 # fila e respostas de cada conta
ARQ_FILA = PASTA_PERFIL / "fila.json"            # ofertas garimpadas e seu status
ARQ_PALAVRAS = PASTA_PERFIL / "palavras.json"    # memória das buscas: quais termos trazem achados
