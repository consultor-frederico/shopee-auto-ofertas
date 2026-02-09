import os
import time
import hashlib
import json
import requests

# 1. CREDENCIAIS 🔐
APP_ID = str(os.getenv('SHOPEE_APP_ID')).strip()
APP_SECRET = str(os.getenv('SHOPEE_APP_SECRET')).strip()
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura_v2(payload, timestamp):
    base = f"{APP_ID}{timestamp}{payload}{APP_SECRET}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_melhores_ofertas():
    timestamp = int(time.time())
    
    # Usando productOfferV2 (conforme sua última documentação)
    # sortType: 5 -> Maior Comissão primeiro
    # limit: 5 -> Trazer 5 produtos
    query = """
    query {
      productOfferV2(limit: 5, sortType: 5) {
        nodes {
          productName
          imageUrl
          offerLink
          priceMin
          commission
          sales
          ratingStar
        }
      }
    }
    """
    
    payload = json.dumps({"query": query}, separators=(',', ':'))
    sig = gerar_assinatura_v2(payload, timestamp)
    
    headers = {
        "Authorization": f"SHA256 Credential={APP_ID}, Signature={sig}, Timestamp={timestamp}",
        "Content-Type": "application/json"
    }
    
    print("🚀 Puxando os 5 produtos que mais pagam comissão...")
    try:
        response = requests.post(API_URL, headers=headers, data=payload)
        res = response.json()
        if 'data' in res and res['data'].get('productOfferV2'):
            return res['data']['productOfferV2']['nodes']
        else:
            print(f"⚠️ Erro: {res.get('errors')}")
            return None
    except Exception as e:
        print(f"💥 Erro técnico: {e}")
        return None

if __name__ == "__main__":
    produtos = buscar_melhores_ofertas()
    
    if produtos:
        # GERANDO CSV PARA EXCEL/MANYCHAT
        with open('integracao_shopee.csv', 'w', encoding='utf-16') as f:
            f.write("produto;preco;comissao_rs;vendas;nota;foto;link\n")
            for p in produtos:
                nome = p['productName'].replace(';', ' ')
                f.write(f"{nome};{p['priceMin']};{p['commission']};{p['sales']};{p['ratingStar']};{p['imageUrl']};{p['offerLink']}\n")
        
        # SALVANDO JSON
        with open('links_do_dia.json', 'w', encoding='utf-8') as j:
            json.dump({"status": "Sucesso", "produtos": produtos}, j, indent=4, ensure_ascii=False)
            
        print(f"✅ Integração completa com {len(produtos)} produtos!")
    else:
        print("❌ Falha na busca.")
