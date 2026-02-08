import os
import time
import hashlib
import json
import requests
from datetime import datetime, timedelta

# 1. CONFIGURAÇÕES 🛡️
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')
affiliate_id = os.getenv('SHOPEE_AFFILIATE_ID') 

CATEGORIAS = [11050227, 11050232, 11050237, 11050242]
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    base_string = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

def converter_link_afiliado(url_original):
    timestamp = int(time.time())
    query = 'mutation{generateShortLink(input:{originUrl:"' + url_original + '",affiliateId:' + str(affiliate_id) + '}){shortLink}}'
    payload = json.dumps({"query": query})
    assinatura = gerar_assinatura(payload, timestamp)
    headers = {"Authorization": f"SHA256 {assinatura}", "Timestamp": str(timestamp), "Content-Type": "application/json"}
    try:
        response = requests.post(API_URL, headers=headers, data=payload).json()
        return response['data']['generateShortLink']['shortLink']
    except:
        return url_original

# 2. MOTOR DE BUSCA EM MODO DE TESTE (SEM TRAVAS) 🔍
def buscar_ofertas_reais():
    novas_ofertas = []
    timestamp = int(time.time())

    for cat_id in CATEGORIAS:
        # Aumentamos o limite para 50 para achar QUALQUER coisa
        query = 'query{productList(categoryId:' + str(cat_id) + ',sortBy:"sales",limit:50,page:1){nodes{itemId,productName,productLink}}}'
        payload = json.dumps({"query": query})
        assinatura = gerar_assinatura(payload, timestamp)
        headers = {"Authorization": f"SHA256 {assinatura}", "Timestamp": str(timestamp), "Content-Type": "application/json"}
        
        try:
            res = requests.post(API_URL, headers=headers, data=payload).json()
            produtos = res['data']['productList']['nodes']
            
            for p in produtos:
                # REMOVEMOS TODAS AS TRAVAS PARA O TESTE
                link_real = converter_link_afiliado(p['productLink'])
                novas_ofertas.append({"nome": p['productName'], "url": link_real})
                
                if len(novas_ofertas) >= 25: break
        except:
            continue
        if len(novas_ofertas) >= 25: break
    return novas_ofertas

# 3. ATUALIZAÇÃO DO ARQUIVO 🚀
def atualizar_arquivo_links(novas_ofertas):
    arquivo = 'links_do_dia.json'
    dados = {} # Começa do zero para o teste
    indice = 1
    for oferta in novas_ofertas:
        dados[f"Oferta_{indice:02d}"] = {
            "produto": oferta['nome'],
            "url": oferta['url'],
            "status": "Teste de Conexão OK",
            "data": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        indice += 1
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    ofertas = buscar_ofertas_reais()
    if ofertas:
        atualizar_arquivo_links(ofertas)
        print(f"Sucesso! {len(ofertas)} links reais capturados.")
    else:
        print("API não retornou nada. Verifique se o SHOPEE_APP_ID está correto.")
