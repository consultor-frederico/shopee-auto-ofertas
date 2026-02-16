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
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
ARQUIVO_HISTORICO = 'historico_completo.json'

def gerar_assinatura_v2(payload, timestamp):
    base = f"{APP_ID}{timestamp}{payload}{APP_SECRET}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def carregar_historico():
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            with open(ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
                historico = json.load(f)
                # --- MELHORIA 1: Limpeza Automática Estrita ---
                # Garante que o histórico não cresça infinitamente e permita repetir itens após 7 dias
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

def produto_pode_repetir(item_id, historico):
    # --- MELHORIA 2: Controle de Ineditismo ---
    # Se não está no histórico (que agora só mantém itens dos últimos 7 dias), pode postar
    return item_id not in historico

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
                # Aplica a lógica de ineditismo
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
        # --- MELHORIA 3: Sobrescrita do CSV para controle do n8n ---
        # Abrimos com 'w' para que o n8n veja apenas os 5 itens inéditos do dia
        with open('integracao_shopee.csv', 'w', encoding='utf-16', newline='') as f:
            f.write("id_shopee;produto;preco;comissao_rs;vendas;nota;link_foto;link_afiliado;data_geracao;status\n")
            for p in novos_produtos:
                nome = p['productName'].replace(';', ' ').replace('\n', '')
                comissao = f"{float(p['commission']):.2f}"
                data_agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{p['itemId']};{nome};{p['priceMin']};{comissao};{p['sales']};{p['ratingStar']};{p['imageUrl']};{p['offerLink']};{data_agora};pendente\n")
        
        with open('links_do_dia.json', 'w', encoding='utf-8') as j:
            json.dump({
                "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "produtos": novos_produtos
            }, j, indent=4, ensure_ascii=False)
        
        salvar_no_historico(historico_base, novos_produtos)
        print("✅ Dados prontos para o n8n via GitHub!")
    else:
        print("❌ Nenhum produto novo encontrado mesmo após 50 páginas.")
