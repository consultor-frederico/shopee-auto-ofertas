import os
import time
import hashlib
import json
import requests

# 1. CREDENCIAIS 🔐
app_id = str(os.getenv('SHOPEE_APP_ID', '18377620107')).strip()
app_secret = str(os.getenv('SHOPEE_APP_SECRET', 'QQZL7L2MOUXDHZFKRBSHFFWNNGGULBYV')).strip()

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def testar_conexao(ordem_v1=True):
    timestamp = int(time.time())
    query = 'query{productOfferList(limit:1){nodes{productName}}}'
    payload = json.dumps({"query": query}, separators=(',', ':'))
    
    # Define a ordem baseada no parâmetro
    if ordem_v1:
        base = f"{app_id}{timestamp}{payload}{app_secret}"
        label = "PADRÃO (Payload antes do Secret)"
    else:
        base = f"{app_id}{timestamp}{app_secret}{payload}"
        label = "INVERTIDA (Secret antes do Payload)"
        
    sig = hashlib.sha256(base.encode('utf-8')).hexdigest()
    
    headers = {
        "Authorization": f"SHA256 {sig}",
        "Timestamp": str(timestamp),
        "Content-Type": "application/json"
    }

    print(f"🧪 Testando Ordem: {label}")
    try:
        response = requests.post(API_URL, headers=headers, data=payload)
        res = response.json()
        if 'data' in res and res.get('data'):
            print(f"✅ SUCESSO na ordem {label}!")
            return res['data']['productOfferList']['nodes']
        else:
            print(f"❌ Falha na ordem {label}: {res.get('errors', [{}])[0].get('message', 'Erro desconhecido')}")
    except Exception as e:
        print(f"💥 Erro técnico: {e}")
    return None

if __name__ == "__main__":
    print(f"🚀 Iniciando Diagnóstico Duplo para AppID: {app_id}")
    
    # Tenta o primeiro método
    resultado = testar_conexao(ordem_v1=True)
    
    # Se falhou, tenta o segundo
    if not resultado:
        resultado = testar_conexao(ordem_v1=False)
    
    # Salva o resultado final
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if resultado:
            json.dump({"status": "Sucesso", "produto": resultado[0]}, f, indent=4)
        else:
            json.dump({"status": "Erro", "detalhes": "Ambas as ordens de assinatura falharam."}, f)
