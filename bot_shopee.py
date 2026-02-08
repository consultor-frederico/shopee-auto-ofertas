import os
import time
import hashlib
import json
import requests

# 1. CREDENCIAIS DIRETAS 🔐
app_id = "18377620107" # Conforme seu print
app_secret = "Z47YUUZINZYEZVV2ZQ7P4QJICKISTOMB" # Conforme seu print
affiliate_id = 18377620107

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def buscar_produtos_simples():
    timestamp = int(time.time())
    # Query minimalista para testar a porta
    query = 'query{productList(limit:5){nodes{productName,productLink}}}'
    payload = json.dumps({"query": query})
    
    # Montagem exata exigida pela documentação: AppID + Timestamp + Payload + AppSecret
    base_string = f"{app_id}{timestamp}{payload}{app_secret}"
    signature = hashlib.sha256(base_string.encode('utf-8')).hexdigest()
    
    headers = {
        "Authorization": f"SHA256 {signature}",
        "Timestamp": str(timestamp),
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, headers=headers, data=payload)
        res = response.json()
        
        if 'data' in res and res['data']['productList']:
            return res['data']['productList']['nodes']
        else:
            print(f"DEBUG SHOPEE: {res}")
            return []
    except Exception as e:
        print(f"Erro: {e}")
        return []

if __name__ == "__main__":
    produtos = buscar_produtos_simples()
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if produtos:
            dados = {f"Produto_{i+1}": p for i, p in enumerate(produtos)}
            json.dump(dados, f, indent=4, ensure_ascii=False)
            print("✅ SUCESSO! Links capturados.")
        else:
            json.dump({"erro": "A Shopee ainda recusa as credenciais. Aguarde 24h ou revise o AppID no Console de Desenvolvedor."}, f)
            print("❌ Falha nas credenciais.")
