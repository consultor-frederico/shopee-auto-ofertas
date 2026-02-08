import os
import time
import hashlib
import json
import requests
from datetime import datetime, timedelta

# 1. CONFIGURAÇÕES E CREDENCIAIS 🔐
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')
affiliate_id = os.getenv('SHOPEE_AFFILIATE_ID') 

# IDs das categorias na ordem escolhida
CATEGORIAS = [11050227, 11050232, 11050237, 11050242]
DIAS_MEMORIA = 7
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura(payload, timestamp):
    base_string = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

def converter_link_afiliado(url_original):
    timestamp = int(time.time())
    query = 'mutation{generateShortLink(input:{originUrl:"' + url_original + '",affiliateId:' + str(affiliate_id) + '}){shortLink}}'
    payload = json.dumps({"query": query})
    
    assinatura = gerar_assinatura(payload, timestamp)
    headers = {
        "Authorization": f"SHA256 {assinatura}",
        "Timestamp": str(timestamp),
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, headers=headers, data=payload).json()
        return response['data']['generateShortLink']['shortLink']
    except:
        return url_original

# 2. SISTEMA DE MEMÓRIA (FILTRO DE IDs) 🆔
def gerenciar_memoria(novo_id=None):
    arquivo = 'historico_ids.json'
    agora = datetime.now()
    try:
        with open(arquivo, 'r') as f:
            memoria = json.load(f)
    except:
        memoria = {}

    # Limpeza automática (7 dias)
    limite = agora - timedelta(days=DIAS_MEMORIA)
    memoria = {k: v for k, v in memoria.items() if datetime.fromisoformat(v) > limite}

    if novo_id:
        if str(novo_id) in memoria: return False
        memoria[str(novo_id)] = agora.isoformat()
        with open(arquivo, 'w') as f:
            json.dump(memoria, f)
        return True
    return memoria

# 3. MOTOR DE BUSCA COM DIAGNÓSTICO 🔍
def buscar_ofertas_reais():
    novas_ofertas = []
    timestamp = int(time.time())

    for cat_id in CATEGORIAS:
        # Buscamos os Top Sellers da categoria
        query = 'query{productList(categoryId:' + str(cat_id) + ',sortBy:"sales",limit:20,page:1){nodes{itemId,productName,productLink}}}'
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
            
            # Verificação de erro da Shopee no log
            if 'errors' in res:
                print(f"❌ ERRO DA SHOPEE (Cat {cat_id}): {res['errors']}")
                continue
                
            if 'data' not in res or not res['data']['productList']:
                print(f"⚠️ RESPOSTA SEM DADOS (Cat {cat_id}): {res}")
                continue

            produtos = res['data']['productList']['nodes']
            for p in produtos:
                if gerenciar_memoria(p['itemId']):
                    link_real = converter_link_afiliado(p['productLink'])
                    novas_ofertas.append({"nome": p['productName'], "url": link_real})
                
                if len(novas_ofertas) >= 25: break
        except Exception as e:
            print(f"🚨 ERRO DE CONEXÃO: {e}")
            continue
        
        if len(novas_ofertas) >= 25: break

    return novas_ofertas

# 4. ATUALIZAÇÃO DO JSON 🚀
def atualizar_arquivo_links(novas_ofertas):
    arquivo = 'links_do_dia.json'
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except:
        dados = {}

    indice = len(dados) + 1
    for oferta in novas_ofertas:
        if indice <= 25:
            dados[f"Oferta_{indice:02d}"] = {
                "produto": oferta['nome'],
                "url": oferta['url'],
                "data": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            indice += 1

    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    print("Iniciando busca dinâmica por categorias...")
    ofertas = buscar_ofertas_reais()
    if ofertas:
        atualizar_arquivo_links(ofertas)
        print(f"Sucesso! {len(ofertas)} novos links reais capturados.")
    else:
        print("Nenhum produto foi adicionado. Verifique os erros acima nos logs.")
