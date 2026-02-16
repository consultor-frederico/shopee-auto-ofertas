import os
import time
import hashlib
import json
import requests
import csv
from datetime import datetime, timedelta

# 1. CREDENCIAIS 🔐
APP_ID = str(os.getenv('SHOPEE_APP_ID')).strip()
APP_SECRET = str(os.getenv('SHOPEE_APP_SECRET')).strip()
GROQ_KEY = os.getenv('GROQ_API_KEY') # Atualizado para usar sua chave do Groq
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
ARQUIVO_HISTORICO = 'historico_completo.json'

def gerar_legenda_ia(nome_produto, preco):
    """ Chama a Groq para transformar o nome feio da Shopee em uma legenda magnética """
    if not GROQ_KEY:
        return nome_produto # Fallback caso a chave não esteja configurada
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"Você é um social media profissional. Transforme este produto da Shopee em uma legenda curta, matadora e com emojis para o Instagram. Use gatilhos de achadinho e promoção. Produto: {nome_produto} - Preço: R$ {preco}"
    
    data = {
        "model": "llama3-8b-8192", # Modelo rápido e excelente para legendas
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        return response.json()['choices'][0]['message']['content'].strip()
    except:
        return nome_produto

def gerar_assinatura_v2(payload, timestamp):
    base = f"{APP_ID}{timestamp}{payload}{APP_SECRET}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def carregar_historico():
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            with open(ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
                historico = json.load(f)
                agora = datetime.now()
                historico_limpo = {}
                for item_id, dados in historico.items():
                    data_str = dados["data"] if isinstance(dados, dict) else dados
                    data_item = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S")
                    if agora - data_item <= timedelta(days=7):
                        historico_limpo[item_id] = dados
                return historico_limpo
        except:
            return {}
    return {}

def salvar_no_historico(historico, novos_produtos):
    data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for p in novos_produtos:
        historico[str(p['itemId'])] = {
            "data": data_hoje,
            "link_afiliado": p['offerLink'],
            "status": "postado"
        }
    with open(ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f:
        json.dump(historico, f, indent=4, ensure_ascii=False)

def buscar_produtos_validos(quantidade=5):
    historico = carregar_historico()
    produtos_filtrados = []
    pagina = 1
    
    while len(produtos_filtrados) < quantidade and pagina <= 50:
        timestamp = int(time.time())
        query = f"""
        query {{
          productOfferV2(limit: 40, sortType: 5, page: {pagina}) {{
            nodes {{
              itemId, productName, imageUrl, offerLink, priceMin, commission, sales, ratingStar
            }}
          }}
        }}
        """
        payload = json.dumps({"query": query}, separators=(',', ':'))
        sig = gerar_assinatura_v2(payload, timestamp)
        headers = {"Authorization": f"SHA256 Credential={APP_ID}, Signature={sig}, Timestamp={timestamp}", "Content-Type": "application/json"}
        
        try:
            response = requests.post(API_URL, headers=headers, data=payload)
            nodes = response.json().get('data', {}).get('productOfferV2', {}).get('nodes', [])
            for p in nodes:
                item_id = str(p['itemId'])
                if item_id not in historico and len(produtos_filtrados) < quantidade:
                    # AQUI ENTRA A IA: Geramos a legenda antes de adicionar à lista
                    p['legenda_ia'] = gerar_legenda_ia(p['productName'], p['priceMin'])
                    produtos_filtrados.append(p)
            pagina += 1
        except: break
    return produtos_filtrados, historico

if __name__ == "__main__":
    novos_produtos, historico_base = buscar_produtos_validos(5)
    
    if novos_produtos:
        with open('integracao_shopee.csv', 'w', encoding='utf-16', newline='') as f:
            f.write("id_shopee;produto;preco;comissao_rs;vendas;nota;link_foto;link_afiliado;data_geracao;status\n")
            for p in novos_produtos:
                # Agora o CSV leva a legenda da IA no lugar do nome bruto
                f.write(f"{p['itemId']};{p['legenda_ia']};{p['priceMin']};{float(p['commission']):.2f};{p['sales']};{p['ratingStar']};{p['imageUrl']};{p['offerLink']};{datetime.now().strftime('%Y-%m-%d %H:%M:%S')};pendente\n")
        
        salvar_no_historico(historico_base, novos_produtos)
        print("✅ Garimpo com IA (Groq) finalizado!")
