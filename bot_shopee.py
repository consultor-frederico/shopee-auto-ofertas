import os
import time
import hashlib
import json
import requests

APP_ID = str(os.getenv('SHOPEE_APP_ID')).strip()
APP_SECRET = str(os.getenv('SHOPEE_APP_SECRET')).strip()
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura_v2(payload, timestamp):
    base = f"{APP_ID}{timestamp}{payload}{APP_SECRET}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_v2():
    timestamp = int(time.time())
    # Aumentamos o limit para 5 e adicionamos videoUrl
    query = 'query{shopeeOfferV2(limit:5){nodes{offerName imageUrl videoUrl offerLink}}}'
    payload = json.dumps({"query": query}, separators=(',', ':'))
    
    sig = gerar_assinatura_v2(payload, timestamp)
    
    headers = {
        "Authorization": f"SHA256 Credential={APP_ID}, Signature={sig}, Timestamp={timestamp}",
        "Content-Type": "application/json"
    }
    
    print("🚀 Buscando 5 ofertas com mídia na v2...")
    try:
        response = requests.post(API_URL, headers=headers, data=payload)
        res = response.json()
        if 'data' in res and res['data'].get('shopeeOfferV2'):
            return res['data']['shopeeOfferV2']['nodes'], "v2"
    except Exception as e:
        print(f"Erro na v2: {e}")
    return None, None

if __name__ == "__main__":
    resultado, versao = buscar_v2()
    
    # Se a v2 falhar, o fallback v1 (que você já tem) pode ser chamado aqui
    # Mas como a v2 é a única que suporta videoUrl de forma nativa e moderna:
    
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if resultado:
            # Salvamos a lista completa de 5 produtos
            json.dump({
                "status": "Sucesso", 
                "total": len(resultado),
                "produtos": resultado 
            }, f, indent=4, ensure_ascii=False)
            print(f"✅ Sucesso! {len(resultado)} produtos salvos.")
        else:
            json.dump({"status": "Erro", "detalhes": "Não foi possível carregar as ofertas."}, f)
            print("❌ Falha na busca.")
