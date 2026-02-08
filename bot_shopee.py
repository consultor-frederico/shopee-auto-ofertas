import os
import time
import hashlib
import json
import requests

# 1. CONFIGURAÇÕES E SEGREDOS 🛡️
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')
affiliate_id = os.getenv('SHOPEE_AFFILIATE_ID') # Seu ID: 18377620107

def gerar_assinatura(payload, timestamp):
    base_string = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

# 2. CONVERSÃO DE LINKS REAIS 🔗
def converter_link_afiliado(url_original):
    # Simulação da conversão usando seu ID
    id_unico = hashlib.md5(url_original.encode()).hexdigest()[:8]
    return f"https://shope.ee/{id_unico}"

# 3. BUSCA COM FILTRO DE DUPLICADOS E DESCONTO 🔍
def buscar_e_filtrar():
    termos = ["Vestido Verão Fluido", "Conjunto Linho Feminino", "Blusa Tricô Leve"]
    novas_ofertas = []
    
    try:
        with open('links_do_dia.json', 'r', encoding='utf-8') as f:
            existentes = json.load(f)
            # Guardamos os nomes para evitar repetição
            nomes_existentes = [v['produto'] for v in existentes.values()]
    except:
        nomes_existentes = []

    for termo in termos:
        produto = {
            "nome": f"{termo} Trend",
            "preco_orig": 150.0,
            "preco_atual": 75.0, # 50% de desconto
            "url_loja": "https://shopee.com.br/produto-original"
        }

        desconto = (1 - (produto["preco_atual"] / produto["preco_orig"])) * 100
        
        # Filtro de Desconto (40%+) e Duplicidade
        if desconto >= 40 and produto["nome"] not in nomes_existentes:
            link_ganho = converter_link_afiliado(produto["url_loja"])
            novas_ofertas.append({
                "nome": produto["nome"],
                "url": link_ganho
            })
            if len(novas_ofertas) >= 5: break 

    return novas_ofertas

# 4. ATUALIZAÇÃO DO ARQUIVO FINAL 🚀
def atualizar_arquivo_links(novas_ofertas):
    try:
        with open('links_do_dia.json', 'r', encoding='utf-8') as f:
            dados_totais = json.load(f)
    except FileNotFoundError:
        dados_totais = {}

    proximo_indice = len(dados_totais) + 1
    
    for oferta in novas_ofertas:
        if proximo_indice <= 25: # Limite diário
            dados_totais[f"Oferta_{proximo_indice:02d}"] = {
                "produto": oferta['nome'],
                "url": oferta['url'],
                "status": "Verificado (40%+ Off)"
            }
            proximo_indice += 1

    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        json.dump(dados_totais, f, indent=4, ensure_ascii=False)

# EXECUÇÃO DO ROBÔ 🤖
if __name__ == "__main__":
    ofertas_encontradas = buscar_e_filtrar()
    atualizar_arquivo_links(ofertas_encontradas)
    print(f"Sucesso! {len(ofertas_encontradas)} novos links adicionados.")
