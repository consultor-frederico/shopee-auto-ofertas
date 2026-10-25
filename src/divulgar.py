"""Manda um vídeo de divulgação (com o texto pronto) para o Telegram PRIVADO do Fred,
para ele repassar nos grupos. Os arquivos ficam em assets/divulgacao/<nome>.mp4 e <nome>.txt.

Uso: python -m src.divulgar <nome>
Segredos: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_PRIVADO.
"""
import json
import os
import sys

from . import config, telegram

PASTA = config.RAIZ / "assets" / "divulgacao"
PAGINA = "https://consultor-frederico.github.io/shopee-auto-ofertas/zap.html?d="


def rodar(nome):
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or not chat:
        print("⏸️  Faltam TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_PRIVADO.")
        return
    video = PASTA / f"{nome}.mp4"
    texto = PASTA / f"{nome}.txt"
    if not video.exists():
        raise RuntimeError(f"Não achei {video.relative_to(config.RAIZ)}.")
    # o "Copiar" do Telegram não leva o vídeo: o botão abre a página que manda vídeo + texto juntos
    compartilhar = {"text": "📲 Compartilhar no WhatsApp", "url": PAGINA + nome}
    legenda = texto.read_text(encoding="utf-8").strip()[:1024] if texto.exists() else ""
    with open(video, "rb") as f:
        telegram._api("sendVideo", data={"chat_id": chat, "caption": legenda, "supports_streaming": "true",
                                         "reply_markup": json.dumps({"inline_keyboard": [[compartilhar]]})},
                      files={"video": f})
    print(f"📲 Enviado: {video.name}")


if __name__ == "__main__":
    try:
        rodar(sys.argv[1] if len(sys.argv) > 1 else "ze_canal_whatsapp")
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
