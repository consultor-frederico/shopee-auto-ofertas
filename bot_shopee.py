import os
import time
import hmac
import hashlib
import json
import requests

# 1. ACESSO SEGURO 🛡️
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')

# 2. FUNÇÃO DE ASSINATURA ✍️
def gerar_assinatura(path):
    timestamp = int(time.time())
    base_string = f"{app_id}{path}{timestamp}"
    signature = hmac.new(
        app_secret.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature, timestamp

# 3. BUSCA DE PRODUTOS 🚀 (Simulação inicial para teste)
def buscar_produtos():
    # No futuro, aqui chamaremos a API real da Shopee
    achados = [
        {"nome": "Smartwatch Trend", "url": "https://shope.ee/ex1", "rating": 4.9, "desconto": 30},
        {"nome": "Fone Wireless", "url": "https://shope.ee/ex2", "rating": 4.8, "desconto": 25}
    ]
    return achados

# 4. SALVAR RESULTADOS 📚
def salvar_links(novos):
    arquivo = 'links_do_dia.json'
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except FileNotFoundError:
        dados = {}

    for item in novos:
        indice = len(dados) + 1
        if indice <= 25:
            dados[f"Link {indice:02d}"] = item

    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    lista = buscar_produtos()
    salvar_links(lista)
    print(f"Sucesso! {len(lista)} produtos processados.")
