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
GROQ_KEY = os.getenv('GROQ_API_KEY') 
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
ARQUIVO_HISTORICO = 'historico_completo.json'
ARQUIVO_CSV = 'integracao_shopee.csv' # Nome do arquivo que o n8n lê

def gerar_legenda_ia(nome_produto, preco):
    """ Chama a Groq para transformar o nome feio da Shopee em uma legenda magnética """
    if not GROQ_KEY:
        print("DEBUG: Chave GROQ_API_KEY não encontrada!")
        return nome_produto 
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = (f"Você é um social media profissional. Escreva uma legenda curta e persuasiva para o Instagram "
              f"sobre este produto: {nome_produto} - Preço: R$ {preco}. "
              f"Use emojis e finalize com a frase: 'Comente EU QUERO que te envio o link!'. "
              f"REGRA CRÍTICA: Escreva tudo em uma única linha, sem quebras de linha ou parágrafos.")
    
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            return nome_produto
        return response.json()['choices'][0]['message']['content'].strip().replace('\n', ' ')
    except Exception as e:
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
                    p['legenda_ia'] = gerar_legenda_ia(p['productName'], p['priceMin'])
                    produtos_filtrados.append(p)
            pagina += 1
        except: break
    return produtos_filtrados, historico

# --- NOVA FUNÇÃO DE LIMPEZA E ATUALIZAÇÃO DO CSV ---
def atualizar_csv_com_limpeza(novos_produtos):
    agora = datetime.now()
    linhas_validas = []
    cabecalho = "id_shopee;produto;preco;comissao_rs;vendas;nota;link_foto;link_afiliado;data_geracao;status;id_instagram"

    # 1. LER O ARQUIVO EXISTENTE E FILTRAR (APENAR O QUE TEM MENOS DE 7 DIAS)
    if os.path.exists(ARQUIVO_CSV):
        with open(ARQUIVO_CSV, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                try:
                    data_geracao = datetime.strptime(row['data_geracao'], "%Y-%m-%d %H:%M:%S")
                    if agora - data_geracao <= timedelta(days=7):
                        linhas_validas.append(row)
                except:
                    continue # Pula se a data estiver errada

    # 2. ADICIONAR OS 5 NOVOS PRODUTOS À LISTA
    for p in novos_produtos:
        nova_linha = {
            "id_shopee": p['itemId'],
            "produto": p['legenda_ia'],
            "preco": p['priceMin'],
            "comissao_rs": f"{float(p['commission']):.2f}",
            "vendas": p['sales'],
            "nota": p['ratingStar'],
            "link_foto": p['imageUrl'],
            "link_afiliado": p['offerLink'],
            "data_geracao": agora.strftime('%Y-%m-%d %H:%M:%S'),
            "status": "pendente",
            "id_instagram": ""
        }
        linhas_validas.append(nova_linha)

    # 3. SALVAR TUDO DE VOLTA NO CSV (SOBRESCREVENDO COM A LISTA LIMPA + NOVOS)
    with open(ARQUIVO_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=cabecalho.split(';'), delimiter=';')
        writer.writeheader()
        writer.writerows(linhas_validas)

if __name__ == "__main__":
    novos_produtos, historico_base = buscar_produtos_validos(5) 
    
    if novos_produtos:
        # Chama a função que limpa o CSV (7 dias) e adiciona os 5 novos
        atualizar_csv_com_limpeza(novos_produtos)
        
        # Mantém o histórico JSON funcionando para o bot não repetir produto
        salvar_no_historico(historico_base, novos_produtos)
        
        print(f"✅ Sucesso! CSV atualizado com {len(novos_produtos)} novas ofertas. Antigas (+7 dias) removidas.")
