import os
import time
import hashlib
import json
import requests
from datetime import datetime

# 1. PEGAR AS CREDENCIAIS (Limpando espaços invisíveis) 🧼
app_id = str(os.getenv('SHOPEE_APP_ID', '')).strip()
app_secret = str(os.getenv('SHOPEE_APP_SECRET', '')).strip()
affiliate_id = str(os.getenv('SHOPEE_AFFILIATE_ID', '')).strip()

API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    base_string = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

def buscar_produtos():
    novas_ofertas = []
    timestamp = int(time.time())
    
    # Suas categorias na ordem: Moda(1), Beleza(2), Eletrônicos(4), Casa(3)
    categorias = [11050227, 11050232, 11050237, 11050242]
    
    for cat_id in categorias:
        query = 'query{productList(categoryId:' + str(cat_id) + ',sortBy:"sales",limit:10,page:1){nodes{itemId,productName,productLink}}}'
        payload = json.dumps({"query": query})
        assinatura = gerar_assinatura(payload, timestamp)
        
        headers = {
            "Authorization": f"SHA256 {assinatura}",
            "Timestamp": str(timestamp),
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(API_URL, headers=headers, data=payload)
            res = response.json()
            
            if 'data' in res and res['data']['productList']:
                produtos = res['data']['productList']['nodes']
                for p in produtos:
                    novas_ofertas.append({
                        "produto": p['productName'],
                        "url": p['productLink']
                    })
                    if len(novas_ofertas) >= 25: break
        except Exception as e:
            print(f"Erro na categoria {cat_id}: {e}")
        
        if len(novas_ofertas) >= 25: break
    return novas_ofertas

if __name__ == "__main__":
    print("🚀 Iniciando busca real na Shopee...")
    ofertas = buscar_produtos()
    
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        if ofertas:
            dados = {f"Oferta_{i+1:02d}": o for i, o in enumerate(ofertas)}
            json.dump(dados, f, indent=4, ensure_ascii=False)
            print(f"✅ SUCESSO! {len(ofertas)} links capturados.")
        else:
            # Se der erro, ele escreve o motivo no arquivo para você ver
            json.dump({"status": "Erro", "motivo": "Credenciais Rejeitadas ou Sem Produtos"}, f)
            print("❌ FALHA: Verifique se o AppID e Secret estão corretos no GitHub.")
