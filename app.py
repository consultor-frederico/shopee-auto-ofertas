from flask import Flask, request
import os
import requests

app = Flask(__name__)

# --- SEGURANÇA ---
# Pegamos as senhas das Configurações do Servidor (não ficam no código)
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')
IG_ACCESS_TOKEN = os.getenv('IG_ACCESS_TOKEN')

@app.route('/', methods=['GET'])
def home():
    return "Robô do Fred está ONLINE e Seguro! 🛡️", 200

# Rota que o Facebook usa para verificar se o robô é real
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    token_sent = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if token_sent == VERIFY_TOKEN:
        return challenge
    return "Token de verificação inválido", 403

# Rota que recebe as mensagens do Instagram
@app.route('/webhook', methods=['POST'])
def receive_message():
    dados = request.json
    
    # Verifica se é uma mensagem válida do Instagram
    try:
        if 'object' in dados and dados['object'] == 'instagram':
            entry = dados['entry'][0]
            messaging = entry['messaging'][0]
            
            sender_id = messaging['sender']['id']
            
            # Se tiver mensagem de texto
            if 'message' in messaging and 'text' in messaging['message']:
                texto_cliente = messaging['message']['text']
                print(f"Mensagem recebida de {sender_id}: {texto_cliente}")
                
                # AQUI ENTRA SUA LÓGICA DE RESPOSTA (IA, ChatGPT, etc)
                enviar_resposta(sender_id, f"Recebi sua mensagem: {texto_cliente}")
                
    except Exception as e:
        print(f"Erro ao processar: {e}")

    return "OK", 200

def enviar_resposta(recipient_id, texto):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={IG_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": texto}
    }
    requests.post(url, json=payload)

if __name__ == '__main__':
    app.run(port=5000)
