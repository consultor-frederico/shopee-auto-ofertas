import os
import time
import hashlib
import json
import requests
from datetime import datetime, timedelta

# 1. CONFIGURAÇÕES DE INTELIGÊNCIA 🧠
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')
affiliate_id = os.getenv('SHOPEE_AFFILIATE_ID') # Seu ID: 18377620107

# IDs das categorias: Moda, Beleza, Eletrônicos, Casa
CATEGORIAS = [11050227, 11050232, 11050237, 11050242]
AVALIACAO_MINIMA = 4.8
DIAS_MEMORIA = 7

def gerar_assinatura(payload, timestamp):
    base_string = f"{app_id}{timestamp}{payload}{app_secret}"
    return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

def converter_link_afiliado(url_original):
    # Simulação da conversão usando seu ID
    id_hash = hashlib.md5(url_original.encode()).hexdigest()[:8]
    return f"https://shope.ee/{id_hash}"

# 2. SISTEMA DE MEMÓRIA (FILTRO DE IDs) 🆔
def gerenciar_memoria(novo_id=None):
    arquivo = 'historico_ids.json'
    agora = datetime.now()
    
    try:
        with open(arquivo, 'r') as f:
            memoria = json.load(f)
    except:
        memoria = {}

    # Limpeza por Tempo: remove IDs com mais de 7 dias
    limite = agora - timedelta(days=DIAS_MEMORIA)
    memoria = {k: v for k, v in memoria.items() if datetime.fromisoformat(v) > limite}

    if novo_id:
        if str(novo_id) in memoria:
            return False # Já postado!
        memoria[str(novo_id)] = agora.isoformat()
        with open(arquivo, 'w') as f:
            json.dump(memoria, f)
        return True
    return memoria

# 3. ESCADA DE LUCRO (COMISSÃO POR PREÇO) 💸
def validar_comissao(preco, taxa_comissao):
    if preco <= 30.0:
        return taxa_comissao >= 0.12 # 12% min
    elif preco <= 150.0:
        return taxa_comissao >= 0.10 # 10% min
    else:
        return taxa_comissao >= 0.05 # 5% min

# 4. MOTOR DE BUSCA DINÂMICO 🔍
def buscar_ofertas_equilibradas():
    novas_ofertas = []
    
    for cat_id in CATEGORIAS:
        # Aqui o robô simula a busca pelos Top Sellers da categoria
        # Na API real, você usaria requests.post com o sort_by: sales
        produtos_ficticios = [
            {"id": f"{cat_id}_1", "nome": "Produto Trend A", "preco": 25.0, "comissao": 0.15, "nota": 4.9, "url": "shopee.com.br/a"},
            {"id": f"{cat_id}_2", "nome": "Produto Trend B", "preco": 80.0, "comissao": 0.11, "nota": 4.8, "url": "shopee.com.br/b"},
        ]

        for p in produtos_ficticios:
            # Aplica todos os nossos filtros automáticos
            if p["nota"] >= AVALIACAO_MINIMA and validar_comissao(p["preco"], p["comissao"]):
                if gerenciar_memoria(p["id"]): # Verifica se é inédito 🆔
                    link = converter_link_afiliado(p["url"])
                    novas_ofertas.append({"nome": p["nome"], "url": link})
            
            if len(novas_ofertas) >= 5: break # 5 por rodada
        if len(novas_ofertas) >= 5: break

    return novas_ofertas

# 5. ATUALIZAÇÃO DO ARQUIVO FINAL 🚀
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
                "status": "Verificado (Qualidade & Lucro)"
            }
            indice += 1

    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    ofertas = buscar_ofertas_equilibradas()
    atualizar_arquivo_links(ofertas)
    print(f"Sucesso! {len(ofertas)} links inéditos adicionados com foco em lucro.")
