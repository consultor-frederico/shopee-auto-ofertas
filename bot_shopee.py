import os
import time
import hmac
import hashlib
import json
import requests

# 1. ACESSO AOS SEGREDOS 🛡️
# O robô busca as chaves que você salvou no "cofre" do GitHub
app_id = os.getenv('SHOPEE_APP_ID')
app_secret = os.getenv('SHOPEE_APP_SECRET')

# 2. FUNÇÃO DE SEGURANÇA (ASSINATURA DIGITAL) ✍️
def gerar_assinatura(path):
    timestamp = int(time.time())
    # A Shopee exige que combinemos o ID, o caminho e o tempo
    base_string = f"{app_id}{path}{timestamp}"
    
    # Criamos o código selado com o seu Secret
    assinatura = hmac.new(
        app_secret.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return assinatura, timestamp

# 3. BUSCA DE PRODUTOS (Geração de Conteúdo) 🚀
def buscar_ofertas():
    # Aqui definimos os termos de pesquisa para os seus nichos 🎯
    termos = ["Smartwatch", "Fone Bluetooth", "Organizador Lar"]
    novos_links = []
    
    # Simulação de processamento (na versão final, conectamos à URL da Shopee)
    for termo in termos:
        produto = {
            "nome": f"{termo} em Oferta",
            "url": "https://shope.ee/exemplo",
            "rating": 4.9,
            "desconto": 30
        }
        # Filtro de qualidade: apenas o que é bom e barato!
        if produto["rating"] >= 4.8 and produto["desconto"] >= 20:
            novos_links.append(produto)
            
    return novos_links

# 4. SALVAR E ACUMULAR LINKS 📚
def salvar_no_arquivo(lista_novos):
    arquivo = 'links_do_dia.json'
    
    # Tenta ler o que já foi salvo hoje
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except FileNotFoundError:
        dados = {}

    # Adiciona os novos links até o limite de 25 por dia 🛍️
    for item in lista_novos:
        posicao = len(dados) + 1
        if posicao <= 25:
            dados[f"Link {posicao:02d}"] = {
                "nome": item["nome"],
                "url": item["url"]
            }

    # Grava de volta no arquivo para o GitHub Actions salvar no repositório
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    print("Iniciando busca automática...")
    ofertas = buscar_ofertas()
    salvar_no_arquivo(ofertas)
    print(f"Finalizado! {len(ofertas)} itens processados com sucesso.")
