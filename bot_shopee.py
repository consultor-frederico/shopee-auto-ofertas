import os
import time
import hashlib
import json
import requests

# 1. CREDENCIAIS 🔐
app_id = str(os.getenv('SHOPEE_APP_ID', '18377620107')).strip()
app_secret = str(os.getenv('SHOPEE_APP_SECRET', 'QQZL7L2MOUXDHZFKRBSHFFWNNGGULBYV')).strip()

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    # Ordem padrão Shopee: AppID + Timestamp + Payload + Secret
    base = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_produtos_em_massa():
    ofertas_finais = []
    timestamp = int(time.time())
    
    # Query simplificada
    query = 'query{productOfferList(limit:5){nodes{productName,offerLink,imageUrl}}}'
    
    # 🎯 LIMPEZA TOTAL: Removemos todos os espaços do JSON (separators)
    payload = json.dumps({"query": query}, separators=(',', ':'))
    
    sig = gerar_assinatura(payload, timestamp)
    
    headers = {
        "Authorization": f"SHA256 {sig}",
        "Timestamp": str(timestamp),
        "Content-Type": "application/json"
    }

    try:
        print(f"🚀 Enviando requisição (AppID: {app_id})...")
        response = requests.post(API_URL, headers=headers, data=payload)
        res = response.json()
        
        if 'data' in res and res.get('data') and res['data'].get('productOfferList'):
            produtos = res['data']['productOfferList']['nodes']
            for p in produtos:
                ofertas_finais.append({
                    "produto": p['productName'],
                    "url": p['offerLink'],
                    "foto": p.get('imageUrl')
                })
        else:
            # Mostra o erro real se falhar
            print(f"❌ Erro da Shopee: {json.dumps(res, indent=2)}")
            
    except Exception as e:
        print(f"Erro de conexão: {e}")
        
    return ofertas_finais

if __name__ == "__main__":
    lista = buscar_produtos_em_massa()
    
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if lista:
            dados = {f"Oferta_{i+1:02d}": o for i, o in enumerate(lista)}
            json.dump(dados, f, indent=4, ensure_ascii=False)
            print(f"✅ SUCESSO! {len(lista)} produtos encontrados.")
        else:
            json.dump({"status": "Erro", "detalhes": "Credenciais rejeitadas pela Shopee."}, f)
            print("❌ Falha na autenticação.")
