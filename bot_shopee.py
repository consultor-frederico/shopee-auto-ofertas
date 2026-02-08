import os
import time
import hashlib
import json
import requests
from datetime import datetime

# Limpeza automática de qualquer espaço que o GitHub possa ter inserido
def get_clean_env(name):
    val = os.getenv(name, '')
    return str(val).strip()

app_id = get_clean_env('SHOPEE_APP_ID')
app_secret = get_clean_env('SHOPEE_APP_SECRET')
affiliate_id = get_clean_env('SHOPEE_AFFILIATE_ID')

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    # A ordem id + timestamp + payload + secret é exigida pela Shopee
    base = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_produtos():
    novas_ofertas = []
    timestamp = int(time.time())
    
    # Categorias: Moda, Beleza, Eletrônicos, Casa
    categorias = [11050227, 11050232, 11050237, 11050242]
    
    for cat_id in categorias:
        query = 'query{productList(categoryId:' + str(cat_id) + ',sortBy:"sales",limit:10,page:1){nodes{itemId,productName,productLink}}}'
        payload = json.dumps({"query": query})
        
        sig = gerar_assinatura(payload, timestamp)
        headers = {
            "Authorization": f"SHA256 {sig}",
            "Timestamp": str(timestamp),
            "Content-Type": "application/json"
        }

        try:
            res = requests.post(API_URL, headers=headers, data=payload).json()
            if 'data' in res and res['data']['productList']:
                for p in res['data']['productList']['nodes']:
                    novas_ofertas.append({"produto": p['productName'], "url": p['productLink']})
            elif 'errors' in res:
                print(f"Erro na Categoria {cat_id}: {res['errors']}")
        except:
            continue
            
        if len(novas_ofertas) >= 25: break
    return novas_ofertas

if __name__ == "__main__":
    ofertas = buscar_produtos()
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if ofertas:
            dados = {f"Oferta_{i+1:02d}": o for i, o in enumerate(ofertas)}
            json.dump(dados, f, indent=4, ensure_ascii=False)
        else:
            json.dump({"erro": "Credenciais Rejeitadas. Verifique AppID e Secret."}, f)
