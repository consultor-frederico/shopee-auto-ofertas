import os
import time
import hashlib
import json
import requests

# 1. CREDENCIAIS (Configuradas nas Secrets do GitHub) 🔐
APP_ID = str(os.getenv('SHOPEE_APP_ID')).strip()
APP_SECRET = str(os.getenv('SHOPEE_APP_SECRET')).strip()
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

def gerar_assinatura_v2(payload, timestamp):
    """Gera a assinatura digital rigorosa da v2 da Shopee."""
    # Ordem obrigatória: AppID + Timestamp + Payload + AppSecret
    base = f"{APP_ID}{timestamp}{payload}{APP_SECRET}"
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def buscar_v2_com_midia():
    """Busca 5 ofertas na API v2 com campos de imagem e vídeo."""
    timestamp = int(time.time())
    
    # Query v2 configurada para 5 itens e todos os tipos de mídia
    query = 'query{shopeeOfferV2(limit:5){nodes{offerName imageUrl videoUrl offerLink}}}'
    
    # Payload limpo (compacto) para não quebrar a assinatura
    payload = json.dumps({"query": query}, separators=(',', ':'))
    
    sig = gerar_assinatura_v2(payload, timestamp)
    
    headers = {
        "Authorization": f"SHA256 Credential={APP_ID}, Signature={sig}, Timestamp={timestamp}",
        "Content-Type": "application/json"
    }
    
    print("🚀 Iniciando busca de 5 ofertas (Reels e Fotos) na v2...")
    try:
        response = requests.post(API_URL, headers=headers, data=payload)
        res = response.json()
        
        if 'data' in res and res['data'].get('shopeeOfferV2'):
            return res['data']['shopeeOfferV2']['nodes']
        else:
            print(f"⚠️ Resposta da Shopee sem dados: {res.get('errors')}")
            return None
    except Exception as e:
        print(f"💥 Erro técnico na conexão: {e}")
        return None

if __name__ == "__main__":
    # Executa a busca
    produtos = buscar_v2_com_midia()
    
    # 2. GERANDO O ARQUIVO DE INTEGRAÇÃO (CSV para Excel/ManyChat) 📊
    # Usamos encoding utf-16 e separador ';' para o Excel brasileiro abrir direto
    nome_arquivo_csv = 'integracao_shopee.csv'
    nome_arquivo_json = 'links_do_dia.json'

    if produtos:
        # Criando o CSV de integração
        with open(nome_arquivo_csv, 'w', encoding='utf-16') as f:
            # Cabeçalho das colunas
            f.write("produto;tem_video;link_video;link_foto;link_afiliado\n")
            
            for p in produtos:
                video = p.get('videoUrl', '')
                tem_video = "SIM" if video else "NÃO"
                # Limpa o nome do produto para não quebrar as colunas do CSV
                nome_limpo = p['offerName'].replace(';', ' ').replace('\n', '')
                
                f.write(f"{nome_limpo};{tem_video};{video};{p['imageUrl']};{p['offerLink']}\n")
        
        # Também salvamos em JSON para manter o histórico que você já tinha
        with open(nome_arquivo_json, 'w', encoding='utf-8') as j:
            json.dump({
                "status": "Sucesso",
                "versao": "v2",
                "total": len(produtos),
                "produtos": produtos
            }, j, indent=4, ensure_ascii=False)
            
        print(f"✅ Sucesso! Arquivos '{nome_arquivo_csv}' e '{nome_arquivo_json}' gerados.")
    else:
        # Se falhar, registra o erro no JSON
        with open(nome_arquivo_json, 'w', encoding='utf-8') as j:
            json.dump({"status": "Erro", "detalhes": "Não foi possível carregar as ofertas."}, j)
        print("❌ Falha na integração. Verifique os logs.")
