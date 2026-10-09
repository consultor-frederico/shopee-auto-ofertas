"""Configurações do Garimpo VIP. Ajuste aqui o nicho, os filtros e o ritmo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
ARQ_FILA = PASTA_DADOS / "fila.json"          # ofertas garimpadas e seu status
FONTE = RAIZ / "assets" / "Montserrat.ttf"
LOGO = RAIZ / "assets" / "logo.png"

# --- Credenciais (segredos do GitHub) ---
SHOPEE_APP_ID = (os.getenv("SHOPEE_APP_ID") or "").strip()
SHOPEE_APP_SECRET = (os.getenv("SHOPEE_APP_SECRET") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
GROQ_URL = "https://api.groq.com/openai/v1"
# Ordem de preferência; se nenhum existir mais, o robô escolhe sozinho um modelo disponível.
GROQ_MODELOS = [m.strip() for m in os.getenv(
    "GROQ_MODELOS", "llama-3.3-70b-versatile,llama-3.1-8b-instant").split(",") if m.strip()]

# --- Nicho: palavras-chave buscadas na Shopee, por categoria ---
NICHO = {
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
    "feminino": [
        "bolsa feminina", "kit maquiagem", "skincare", "escova secadora",
        "prancha alisadora", "brinco feminino", "relógio feminino", "vestido feminino",
        "organizador de maquiagem", "kit pincel maquiagem", "sandália feminina", "colar feminino",
        "massageador facial", "escova alisadora", "organizador de joias", "espelho led",
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

# --- Filtros de qualidade (calibrados com amostra de 7.161 produtos, out/2026) ---
# Ouro: vai para o Instagram. Prata: vai para o Telegram. Abaixo de Prata: descartado.
NIVEIS = {
    "ouro": {"vendas": 1000, "comissao_rs": 8.0, "comissao_pct": 10.0, "uau": 7},
    "prata": {"vendas": 500, "comissao_rs": 5.0, "comissao_pct": 8.0, "uau": 6},
}
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
PALAVRAS_POR_GARIMPO = int(os.getenv("PALAVRAS_POR_GARIMPO", "16"))
DIAS_SEM_REPETIR = 30          # Instagram: não repete o mesmo produto dentro desse prazo
DIAS_SEM_REPETIR_TELEGRAM = 14 # Telegram: campeão de vendas pode voltar depois disso
DIAS_VALIDADE_PENDENTE = 3     # oferta não postada vence depois disso (preço muda)

MARCA = "GARIMPO VIP"
ARROBA = "@garimpovip4"
