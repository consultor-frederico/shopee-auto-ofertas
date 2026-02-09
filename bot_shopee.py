import os
import time
import hashlib
import json
import requests

# 1. CREDENCIAIS 🔐
app_id = str(os.getenv('SHOPEE_APP_ID', '18377620107')).strip()
app_secret = str(os.getenv('SHOPEE_APP_SECRET', 'Z47YUUZINZYEZVV2ZQ7P4QJICKISTOMB')).strip()

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    base = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_produtos_em_massa():
    ofertas_finais = []
    timestamp = int(time.time())
    
    # Query relaxada: traz os 50 mais vendidos sem filtro de nota
    query = 'query{productOfferList(limit:50,sortBy:"sales"){nodes{productName,offerLink}}}'
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
        
        if 'data' in res and res['data'] and res['data']['productOfferList']:
            produtos = res['data']['productOfferList']['nodes']
            for p in produtos:
                ofertas_finais.append({
                    "produto": p['productName'],
                    "url": p['offerLink']
                })
        else:
            print(f"Aviso: A API não retornou produtos. Verifique o Explorer. Erro: {res}")
    except Exception as e:
        print(f"Erro de conexão: {e}")
        
    return ofertas_finais

if __name__ == "__main__":
    print("🚀 Iniciando busca com critérios flexíveis para máximo volume...")
    lista = buscar_produtos_em_massa()
    
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if lista:
            # Pega os 25 primeiros da lista de 50
            dados = {f"Oferta_{i+1:02d}": o for i, o in enumerate(lista[:25])}
            json.dump(dados, f, indent=4, ensure_ascii=False)
            print(f"✅ SUCESSO! {len(lista[:25])} links gerados com sucesso.")
        else:
            json.dump({"status": "Aguardando", "detalhes": "API conectada, aguardando propagação de produtos."}, f)
            print("❌ Nenhuma oferta encontrada ainda.")
