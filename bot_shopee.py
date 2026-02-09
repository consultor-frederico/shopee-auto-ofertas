import os
import time
import hashlib
import json
import requests

# 1. CREDENCIAIS (Pegando das Secrets do GitHub) 🔐
APP_ID = str(os.getenv('SHOPEE_APP_ID')).strip()
APP_SECRET = str(os.getenv('SHOPEE_APP_SECRET')).strip()
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura_v2(payload, timestamp):
    # Ordem v2: AppID + Timestamp + Payload + AppSecret
    base = f"{APP_ID}{timestamp}{payload}{APP_SECRET}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_v2():
    timestamp = int(time.time())
    # Query v2 que escolhemos: Nome, Imagem e Link
    query = 'query{shopeeOfferV2(limit:1){nodes{offerName imageUrl offerLink}}}'
    payload = json.dumps({"query": query}, separators=(',', ':'))
    
    sig = gerar_assinatura_v2(payload, timestamp)
    
    headers = {
        "Authorization": f"SHA256 Credential={APP_ID}, Signature={sig}, Timestamp={timestamp}",
        "Content-Type": "application/json"
    }
    
    print("🚀 Tentando API v2...")
    response = requests.post(API_URL, headers=headers, data=payload)
    res = response.json()
    
    if 'data' in res and res['data'].get('shopeeOfferV2'):
        return res['data']['shopeeOfferV2']['nodes'], "v2"
    return None, res.get('errors')

def buscar_v1_fallback():
    # Sua lógica original de v1 como Plano B
    timestamp = int(time.time())
    query = 'query{productOfferList(limit:1){nodes{productName}}}'
    payload = json.dumps({"query": query}, separators=(',', ':'))
    
    base = f"{APP_ID}{timestamp}{payload}{APP_SECRET}"
    sig = hashlib.sha256(base.encode('utf-8')).hexdigest()
    
    headers = {
        "Authorization": f"SHA256 {sig}",
        "Timestamp": str(timestamp),
        "Content-Type": "application/json"
    }
    
    print("🔄 v2 falhou. Tentando Fallback v1...")
    response = requests.post(API_URL, headers=headers, data=payload)
    res = response.json()
    
    if 'data' in res and res['data'].get('productOfferList'):
        return res['data']['productOfferList']['nodes'], "v1"
    return None, res.get('errors')

if __name__ == "__main__":
    resultado, versao = buscar_v2()
    
    if not resultado:
        resultado, erro_v1 = buscar_v1_fallback()
        versao = "v1" if resultado else "ERRO_TOTAL"

    # SALVAR RESULTADOS (Para o GitHub Action comitar)
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if resultado:
            json.dump({"status": "Sucesso", "versao": versao, "produto": resultado[0]}, f, indent=4)
            print(f"✅ Sucesso via {versao}!")
        else:
            json.dump({"status": "Erro", "detalhes": "Falha total nas APIs"}, f, indent=4)
            print("❌ Falha crítica em ambas as versões.")
