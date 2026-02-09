import os
import time
import hashlib
import json
import requests

# 1. CREDENCIAIS 🔐
app_id = str(os.getenv('SHOPEE_APP_ID', '18377620107')).strip()
app_secret = str(os.getenv('SHOPEE_APP_SECRET', 'QQZL7L2MOUXDHZFKRBSHFFWNNGGULBYV')).strip()

# 🧪 TESTE DE DIAGNÓSTICO:
print(f"DIAGNÓSTICO: O AppID enviado tem {len(app_id)} caracteres.")
print(f"DIAGNÓSTICO: O AppSecret enviado tem {len(app_secret)} caracteres.")

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    # Montamos a base combinando os dados
    base = f"{app_id}{timestamp}{payload}{app_secret}"
    
    # 🔍 NOVO DIAGNÓSTICO: Verificamos a estrutura da assinatura sem expor a senha toda
    print(f"DIAGNÓSTICO: Gerando assinatura para AppID {app_id} no Timestamp {timestamp}")
    print(f"DIAGNÓSTICO: Início da base: {base[:20]}... Fim da base: ...{base[-10:]}")
    
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_produtos_em_massa():
    ofertas_finais = []
    timestamp = int(time.time())
    
    # Query simplificada para teste
    query = 'query{productOfferList(limit:5){nodes{productName,offerLink,imageUrl}}}'
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
        
        print(f"DEBUG - Status Code: {response.status_code}")
        print(f"DEBUG - Resposta da Shopee: {json.dumps(res, indent=2)}")
        
        if 'data' in res and res['data'] and res['data']['productOfferList']:
            produtos = res['data']['productOfferList']['nodes']
            for p in produtos:
                ofertas_finais.append({
                    "produto": p['productName'],
                    "url": p['offerLink'],
                    "foto": p.get('imageUrl')
                })
        else:
            print("Aviso: A API não retornou o formato de dados esperado.")
    except Exception as e:
        print(f"Erro de conexão: {e}")
        
    return ofertas_finais

if __name__ == "__main__":
    print("🚀 Iniciando busca em Modo de Diagnóstico Avançado...")
    lista = buscar_produtos_em_massa()
    
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if lista:
            dados = {f"Oferta_{i+1:02d}": o for i, o in enumerate(lista)}
            json.dump(dados, f, indent=4, ensure_ascii=False)
            print(f"✅ SUCESSO! {len(lista)} produtos encontrados.")
        else:
            json.dump({"status": "Erro", "detalhes": "Verificar log do GitHub Actions."}, f)
            print("❌ Nenhuma oferta encontrada. Cheque o log.")
