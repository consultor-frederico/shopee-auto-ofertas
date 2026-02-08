import os
import time
import hashlib
import json
import requests
from datetime import datetime

# 1. CREDENCIAIS DIRETAS DO GITHUB 🔐
# Certifique-se de que no GitHub o APP_ID seja: 18377620107
# E o APP_SECRET seja: Z47YUUZINZYEZVV2ZQ7P4QJICKISTOMB
app_id = str(os.getenv('SHOPEE_APP_ID', '')).strip()
app_secret = str(os.getenv('SHOPEE_APP_SECRET', '')).strip()
affiliate_id = str(os.getenv('SHOPEE_AFFILIATE_ID', '')).strip()

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    # A ordem dos fatores aqui altera o produto! 
    # id + timestamp + payload + secret
    base = app_id + str(timestamp) + payload + app_secret
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_produtos():
    novas_ofertas = []
    timestamp = int(time.time())
    
    # Vamos testar apenas com UMA categoria para não sobrecarregar
    cat_id = 11050227 # Moda
    
    # Query simplificada ao máximo
    query = 'query{productList(categoryId:' + str(cat_id) + ',limit:10){nodes{productName,productLink}}}'
    payload = json.dumps({"query": query})
    
    sig = gerar_assinatura(payload, timestamp)
    
    headers = {
        "Authorization": f"SHA256 {sig}",
        "Timestamp": str(timestamp),
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, headers=headers, data=payload)
        res = response.json()
        
        if 'data' in res and res['data'] and res['data']['productList']:
            produtos = res['data']['productList']['nodes']
            for p in produtos:
                novas_ofertas.append({
                    "produto": p['productName'],
                    "url": p['productLink']
                })
        else:
            print(f"DEBUG: {res}") # Isso vai nos mostrar o erro real no log
    except Exception as e:
        print(f"Erro de conexão: {e}")
        
    return novas_ofertas

if __name__ == "__main__":
    print(f"Tentando conexão com ID: {app_id[:4]}... e Secret: {app_secret[:4]}...")
    ofertas = buscar_produtos()
    
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if ofertas:
            dados = {f"Oferta_{i+1:02d}": o for i, o in enumerate(ofertas)}
            json.dump(dados, f, indent=4, ensure_ascii=False)
            print(f"✅ SUCESSO! {len(ofertas)} links capturados.")
        else:
            json.dump({"status": "Erro", "motivo": "API recusou as chaves fornecidas"}, f)
            print("❌ Falha crítica nas credenciais.")
