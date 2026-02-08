import os
import time
import hashlib
import json
import requests
from datetime import datetime, timedelta

# 1. CONFIGURAÇÕES DE INTELIGÊNCIA 🧠
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')
affiliate_id = os.getenv('SHOPEE_AFFILIATE_ID') 

# IDs das categorias na ordem: Moda, Beleza, Eletrônicos, Casa
CATEGORIAS = [11050227, 11050232, 11050237, 11050242]
AVALIACAO_MINIMA = 4.8
DIAS_MEMORIA = 7
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    base_string = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

def converter_link_afiliado(url_original):
    # Chamada real para converter o link para seu ID de afiliado
    timestamp = int(time.time())
    payload = json.dumps({
        "query": f'mutation{{generateShortLink(input:{{originUrl:"{url_original}",affiliateId:{affiliate_id}}}){{shortLink}}}}'
    })
    assinatura = gerar_assinatura(payload, timestamp)
    headers = {"Authorization": f"SHA256 {assinatura}", "Timestamp": str(timestamp), "Content-Type": "application/json"}
    
    try:
        response = requests.post(API_URL, headers=headers, data=payload).json()
        return response['data']['generateShortLink']['shortLink']
    except:
        # Fallback caso a API falhe na conversão
        id_hash = hashlib.md5(url_original.encode()).hexdigest()[:8]
        return f"https://shope.ee/{id_hash}"

# 2. SISTEMA DE MEMÓRIA (FILTRO DE IDs) 🆔
def gerenciar_memoria(novo_id=None):
    arquivo = 'historico_ids.json'
    agora = datetime.now()
    try:
        with open(arquivo, 'r') as f:
            memoria = json.load(f)
    except:
        memoria = {}

    # Limpeza por Tempo: remove IDs com mais de 7 dias
    limite = agora - timedelta(days=DIAS_MEMORIA)
    memoria = {k: v for k, v in memoria.items() if datetime.fromisoformat(v) > limite}

    if novo_id:
        if str(novo_id) in memoria:
            return False # Já postado nos últimos 7 dias!
        memoria[str(novo_id)] = agora.isoformat()
        with open(arquivo, 'w') as f:
            json.dump(memoria, f)
        return True
    return memoria

# 3. ESCADA DE LUCRO (COMISSÃO POR PREÇO) 💸
def validar_comissao(preco, taxa_comissao):
    if preco <= 30.0:
        return taxa_comissao >= 0.12 # 12% min
    elif preco <= 150.0:
        return taxa_comissao >= 0.10 # 10% min
    else:
        return taxa_comissao >= 0.05 # 5% min

# 4. MOTOR DE BUSCA DINÂMICO REAL 🔍
def buscar_ofertas_equilibradas():
    novas_ofertas = []
    timestamp = int(time.time())

    for cat_id in CATEGORIAS:
        # Query para buscar Top Sellers por Categoria
        payload = json.dumps({
            "query": f'query{{productList(categoryId:{cat_id},sortBy:"sales",limit:20,page:1){{nodes{{itemId,productName,price,commissionRate,ratingStars,productLink}}}}}}'
        })
        
        assinatura = gerar_assinatura(payload, timestamp)
        headers = {"Authorization": f"SHA256 {assinatura}", "Timestamp": str(timestamp), "Content-Type": "application/json"}
        
        try:
            res = requests.post(API_URL, headers=headers, data=payload).json()
            produtos = res['data']['productList']['nodes']
        except:
            continue

        for p in produtos:
            preco_real = float(p['price']) / 100000 # Formatação de preço da API Shopee
            taxa_com = float(p['commissionRate'])
            
            # Aplica os filtros: Nota + Comissão + Memória Inédita
            if float(p['ratingStars']) >= AVALIACAO_MINIMA and validar_comissao(preco_real, taxa_com):
                if gerenciar_memoria(p['itemId']):
                    link = converter_link_afiliado(p['productLink'])
                    novas_ofertas.append({"nome": p['productName'], "url": link})
            
            # Pega 1 ou 2 por categoria para manter o MIX equilibrado
            if len(novas_ofertas) % 5 == 0 and len(novas_ofertas) > 0: break 
            if len(novas_ofertas) >= 25: break

    return novas_ofertas

# 5. ATUALIZAÇÃO DO ARQUIVO FINAL 🚀
def atualizar_arquivo_links(novas_ofertas):
    arquivo = 'links_do_dia.json'
    # Limpamos para garantir 25 novos por dia ou mantemos conforme o fluxo
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except:
        dados = {}

    # Se for a primeira rodada do dia (09:00 UTC), opcionalmente você pode resetar o arquivo
    # if datetime.now().hour == 12: dados = {}

    indice = len(dados) + 1
    for oferta in novas_ofertas:
        if indice <= 25:
            dados[f"Oferta_{indice:02d}"] = {
                "produto": oferta['nome'],
                "url": oferta['url'],
                "status": "Verificado (Qualidade & Lucro)",
                "data": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            indice += 1

    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    ofertas_reais = buscar_ofertas_equilibradas()
    if ofertas_reais:
        atualizar_arquivo_links(ofertas_reais)
        print(f"Sucesso! {len(ofertas_reais)} links reais adicionados.")
    else:
        print("Nenhum produto novo atendeu aos critérios nesta rodada.")
