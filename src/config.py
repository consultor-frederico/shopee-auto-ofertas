"""Configurações do Garimpo VIP. Ajuste aqui o nicho, os filtros e o ritmo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
PASTA_POSTS = RAIZ / "posts"
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
    ],
    "lar": [
        "organizador cozinha", "luminária led", "air fryer acessórios", "jogo de panelas",
        "organizador guarda roupa", "mop giratório", "fita led", "potes herméticos",
        "umidificador", "aspirador portátil", "utensílios cozinha", "tapete banheiro",
    ],
    "brinquedos": [
        "brinquedo educativo", "blocos de montar", "carrinho controle remoto",
        "boneca", "quebra cabeça infantil", "massinha de modelar", "pista hot wheels",
        "brinquedo montessori", "kit slime", "jogo de tabuleiro",
    ],
}

# --- Filtros de qualidade ---
NOTA_MINIMA = float(os.getenv("NOTA_MINIMA", "4.7"))
VENDAS_MINIMAS = int(os.getenv("VENDAS_MINIMAS", "100"))
COMISSAO_MINIMA_RS = float(os.getenv("COMISSAO_MINIMA_RS", "2.0"))
PRECO_MAXIMO = float(os.getenv("PRECO_MAXIMO", "300"))
# Palavras que barram o produto (fora do nicho ou arriscadas para anunciar)
PALAVRAS_PROIBIDAS = [
    "réplica", "replica", "vape", "cigarro", "arma", "faca tática", "sex", "erótic",
    "lingerie", "remédio", "emagrecedor", "suplemento",
]

# --- Ritmo ---
OFERTAS_POR_GARIMPO = int(os.getenv("OFERTAS_POR_GARIMPO", "8"))
PALAVRAS_POR_GARIMPO = int(os.getenv("PALAVRAS_POR_GARIMPO", "6"))
DIAS_SEM_REPETIR = 30          # não repete o mesmo produto dentro desse prazo
DIAS_VALIDADE_PENDENTE = 3     # oferta não postada vence depois disso (preço muda)

MARCA = "GARIMPO VIP"
ARROBA = "@garimpovip4"
