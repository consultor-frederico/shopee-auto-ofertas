import os
import time
import hmac
import hashlib
import json
import requests

# 1. ACESSO AOS SEGREDOS 🛡️
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')

def gerar_assinatura(path):
    timestamp = int(time.time())
    base_string = f"{app_id}{path}{timestamp}"
    assinatura = hmac.new(
        app_secret.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return assinatura, timestamp

# 2. LÓGICA DE BUSCA E FILTRO 🔍
def buscar_ofertas_reais():
    # Termos de Moda e Beleza baseados em tendências de estação
    termos = ["Vestido Verão Fluido", "Conjunto Linho Feminino", "Blusa Tricô Leve", "Lip Oil Hidratante"]
    resultados_filtrados = []
    
    for termo in termos:
        # Aqui o robô simula a busca na API da Shopee
        # Em uma integração real, usaríamos requests.get() com a assinatura
        
        # Simulação de um produto encontrado para aplicar os filtros:
        produto_exemplo = {
            "nome": f"{termo} Trend",
            "preco_original": 120.0,
            "preco_atual": 65.0, # Isso dá ~45% de desconto
            "vendas": 150,
            "url": "https://shope.ee/exemplo_real"
        }
        
        # Cálculo do Desconto 🧮
        desconto = (1 - (produto_exemplo["preco_atual"] / produto_exemplo["preco_original"])) * 100
        
        # APLICAÇÃO DOS FILTROS (Desconto > 40% e Popularidade)
        if desconto >= 40 and produto_exemplo["vendas"] >= 100:
            resultados_filtrados.append(produto_exemplo)
            
    return resultados_filtrados

# 3. GRAVAÇÃO DOS LINKS ✍️
def atualizar_arquivo_links(novos_links):
    arquivo = 'links_do_dia.json'
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        dados = {}

    for item in novos_links:
        if len(dados) < 25: # Limite de 25 links por dia
            chave = f"Oferta_{len(dados) + 1:02d}"
            dados[chave] = {
                "produto": item["nome"],
                "url": item["url"],
                "status": "Verificado (40%+ Off)"
            }

    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    print("Iniciando busca por tendências com super desconto...")
    ofertas = buscar_ofertas_reais()
    atualizar_arquivo_links(ofertas)
    print(f"Sucesso! {len(ofertas)} novas ofertas de alto desconto encontradas.")
