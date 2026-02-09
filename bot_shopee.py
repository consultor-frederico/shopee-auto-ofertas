import os
import time
import hashlib
import json
import requests
from datetime import datetime

# 1. CREDENCIAIS 🔐
app_id = str(os.getenv('SHOPEE_APP_ID', '')).strip()
app_secret = str(os.getenv('SHOPEE_APP_SECRET', '')).strip()
affiliate_id = str(os.getenv('SHOPEE_AFFILIATE_ID', '')).strip()

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    base = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_e_gerar_links():
    novas_ofertas = []
    timestamp = int(time.time())
    
    # Query atualizada conforme a sugestão da API Shopee
    query = 'query{productOfferList(limit:25,sortBy:"sales"){nodes{productName,offerLink}}}'
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
        
        if 'data' in res and res['data']['productOfferList']:
            produtos = res['data']['productOfferList']['nodes']
            for p in produtos:
                novas_ofertas.append({
                    "produto": p['productName'],
                    "url": p['offerLink'],
                    "status": "Link de Afiliado Ativo"
                })
        else:
            print(f"Erro na resposta: {res}")
    except Exception as e:
        print(f"Erro de conexão: {e}")
        
    return novas_ofertas

if __name__ == "__main__":
    print("🚀 Buscando ofertas com o novo campo 'productOfferList'...")
    ofertas = buscar_e_gerar_links()
    
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if ofertas:
            dados = {f"Oferta_{i+1:02d}": o for i, o in enumerate(ofertas)}
            json.dump(dados, f, indent=4, ensure_ascii=False)
            print(f"✅ SUCESSO! {len(ofertas)} ofertas capturadas.")
        else:
            json.dump({"status": "Erro", "detalhes": "API aceitou login, mas não retornou produtos"}, f)
            print("❌ Falha: A API não retornou dados de produtos.")
