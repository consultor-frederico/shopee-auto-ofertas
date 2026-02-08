import os
import time
import hashlib
import json
import requests
from datetime import datetime, timedelta

# 1. CONFIGURAÇÕES 🧠
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')
affiliate_id = os.getenv('SHOPEE_AFFILIATE_ID') 

# Ajustamos para ser mais fácil de encontrar produtos no teste
CATEGORIAS = [11050227, 11050232, 11050237, 11050242]
AVALIACAO_MINIMA = 4.5  # Baixamos de 4.8 para 4.5
DIAS_MEMORIA = 7
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    base_string = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

def converter_link_afiliado(url_original):
    timestamp = int(time.time())
    # Query real para conversão de link
    query = 'mutation{generateShortLink(input:{originUrl:"' + url_original + '",affiliateId:' + str(affiliate_id) + '}){shortLink}}'
    payload = json.dumps({"query": query})
    
    assinatura = gerar_assinatura(payload, timestamp)
    headers = {"Authorization": f"SHA256 {assinatura}", "Timestamp": str(timestamp), "Content-Type": "application/json"}
    
    try:
        response = requests.post(API_URL, headers=headers, data=payload).json()
        link = response['data']['generateShortLink']['shortLink']
        return link if link else url_original
    except:
        return url_original

def gerenciar_memoria(novo_id=None):
    arquivo = 'historico_ids.json'
    agora = datetime.now()
    try:
        with open(arquivo, 'r') as f:
            memoria = json.load(f)
    except:
        memoria = {}

    limite = agora - timedelta(days=DIAS_MEMORIA)
    memoria = {k: v for k, v in memoria.items() if datetime.fromisoformat(v) > limite}

    if novo_id:
        if str(novo_id) in memoria: return False
        memoria[str(novo_id)] = agora.isoformat()
        with open(arquivo, 'w') as f:
            json.dump(memoria, f)
        return True
    return memoria

def buscar_ofertas_reais():
    novas_ofertas = []
    timestamp = int(time.time())

    for cat_id in CATEGORIAS:
        # Buscando 50 produtos para ter mais chance de passar no filtro
        query = 'query{productList(categoryId:' + str(cat_id) + ',sortBy:"sales",limit:50,page:1){nodes{itemId,productName,price,commissionRate,ratingStars,productLink}}}'
        payload = json.dumps({"query": query})
        
        assinatura = gerar_assinatura(payload, timestamp)
        headers = {"Authorization": f"SHA256 {assinatura}", "Timestamp": str(timestamp), "Content-Type": "application/json"}
        
        try:
            res = requests.post(API_URL, headers=headers, data=payload).json()
            produtos = res['data']['productList']['nodes']
            
            for p in produtos:
                # Filtro simplificado para o teste funcionar: Nota 4.5+ e qualquer comissão
                if float(p['ratingStars']) >= AVALIACAO_MINIMA:
                    if gerenciar_memoria(p['itemId']):
                        link_real = converter_link_afiliado(p['productLink'])
                        novas_ofertas.append({"nome": p['productName'], "url": link_real})
                
                if len(novas_ofertas) >= 25: break
        except:
            continue
        if len(novas_ofertas) >= 25: break

    return novas_ofertas

def atualizar_arquivo_links(novas_ofertas):
    arquivo = 'links_do_dia.json'
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except:
        dados = {}

    indice = len(dados) + 1
    for oferta in novas_ofertas:
        if indice <= 25:
            dados[f"Oferta_{indice:02d}"] = {
                "produto": oferta['nome'],
                "url": oferta['url'],
                "data": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            indice += 1

    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    ofertas = buscar_ofertas_reais()
    if ofertas:
        atualizar_arquivo_links(ofertas)
        print(f"Sucesso! {len(ofertas)} links reais convertidos.")
    else:
        print("Nenhum produto encontrado. Verifique suas credenciais da API.")
