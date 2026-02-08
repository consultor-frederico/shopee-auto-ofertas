import os
import json

def iniciar_robo():
    # Puxa suas chaves dos Secrets que você já salvou
    app_id = os.getenv('SHOPEE_APP_ID')
    
    # Cria uma lista de teste para confirmarmos que funciona
    dados = {
        "Link 01": {"produto": "Produto Teste", "url": "https://shopee.com.br"}
    }
    
    with open('links_do_dia.json', 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)
    
    print(f"Robô {app_id} executado com sucesso!")

if __name__ == "__main__":
    iniciar_robo()
