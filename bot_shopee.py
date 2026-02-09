import os
import time
import hashlib
import json
import requests
from datetime import datetime, timedelta

# 1. CREDENCIAIS 🔐
APP_ID = str(os.getenv('SHOPEE_APP_ID')).strip()
APP_SECRET = str(os.getenv('SHOPEE_APP_SECRET')).strip()
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
# UNIFICADO PARA O NOME QUE O GIT ESTÁ SALVANDO
ARQUIVO_HISTORICO = 'historico_completo.json'

def gerar_assinatura_v2(payload, timestamp):
    base = f"{APP_ID}{timestamp}{payload}{APP_SECRET}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def carregar_historico():
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            with open(ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_no_historico(historico, novos_produtos):
    data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for p in novos_produtos:
        historico[str(p['itemId'])] = data_hoje
    
    with open(ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f:
        json.dump(historico, f, indent=4, ensure_ascii=False)

def produto_pode_repetir(item_id, historico):
    if item_id not in historico:
        return True
    data_postagem = datetime.strptime(historico[item_id], "%Y-%m-%d %H:%M:%S")
    if datetime.now() - data_postagem > timedelta(days=7):
        return True
    return False

def buscar_produtos_validos(quantidade=5):
    historico = carregar_historico()
    produtos_filtrados = []
    pagina = 1
    
    # Lista expandida com as categorias que mais saem (Beleza, Casa, Eletrônicos, Moda, Bebês, etc.)
    categorias_bombando = [
        11035544, 11035179, 11034471, 11035031, 11035314, 
        11034547, 11035017, 11034626, 11034491, 11035238, 
        11034870, 11034731, 11034493, 11035417, 11035205
    ]
    
    while len(produtos_filtrados) < quantidade and pagina <= 10:
        timestamp = int(time.time())
        # Ajustado para buscar mais ofertas (limit: 40) conforme solicitado
        query = f"""
        query {{
          productOfferV2(limit: 40, sortType: 5, page: {pagina}, categoryIds: {categorias_bombando}) {{
            nodes {{
              itemId
              productName
              imageUrl
              offerLink
              priceMin
              commission
              sales
              ratingStar
            }}
          }}
        }}
        """
        payload = json.dumps({"query": query}, separators=(',', ':'))
        sig = gerar_assinatura_v2(payload, timestamp)
        
        headers = {
            "Authorization": f"SHA256 Credential={APP_ID}, Signature={sig}, Timestamp={timestamp}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(API_URL, headers=headers, data=payload)
            res = response.json()
            nodes = res.get('data', {}).get('productOfferV2', {}).get('nodes', [])
            
            for p in nodes:
                item_id = str(p['itemId'])
                if produto_pode_repetir(item_id, historico) and len(produtos_filtrados) < quantidade:
                    produtos_filtrados.append(p)
            
            pagina += 1
        except Exception as e:
            print(f"Erro: {e}")
            break

    return produtos_filtrados, historico

if __name__ == "__main__":
    novos_produtos, historico_base = buscar_produtos_validos(5)
    
    if novos_produtos:
        with open('integracao_shopee.csv', 'w', encoding='utf-16') as f:
            f.write("produto;preco;comissao_rs;vendas;nota;link_foto;link_afiliado\n")
            for p in novos_produtos:
                nome = p['productName'].replace(';', ' ').replace('\n', '')
                comissao = f"{float(p['commission']):.2f}"
                f.write(f"{nome};{p['priceMin']};{comissao};{p['sales']};{p['ratingStar']};{p['imageUrl']};{p['offerLink']}\n")
        
        with open('links_do_dia.json', 'w', encoding='utf-8') as j:
            json.dump({
                "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "produtos": novos_produtos
            }, j, indent=4, ensure_ascii=False)
        
        salvar_no_historico(historico_base, novos_produtos)
        print("✅ Dados prontos para o Make!")
