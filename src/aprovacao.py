"""Aprovação pelo Telegram privado: você responde "ok <id>" no bot e a oferta fica aprovada.

Só obedece mensagens vindas do SEU chat privado (TELEGRAM_CHAT_PRIVADO), nunca de outro chat.
Esta etapa só marca a oferta como aprovada e responde com a confirmação. A postagem no
Instagram vem numa etapa seguinte (a arte precisa estar publicada no site antes).

Uso: python -m src.aprovacao
Segredos: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_PRIVADO.
"""
import json
import os
import re
import sys

from . import config, direct_telegram, telegram
from .garimpar import agora, carregar_fila, salvar_fila

ARQ_ESTADO = config.PASTA_PERFIL / "aprovacao.json"   # último update lido, para não repetir comandos
RE_OK = re.compile(r"^\s*ok\s+(\S+)\s*$", re.I)


def _estado():
    if ARQ_ESTADO.exists():
        return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
    return {"ultimo_update": 0}


def _salvar_estado(est):
    ARQ_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQ_ESTADO.write_text(json.dumps(est, ensure_ascii=False, indent=2), encoding="utf-8")


def _responder(chat, texto):
    telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"})


def rodar():
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or not chat:
        print("⏸️  Faltam TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_PRIVADO — aprovação em espera.")
        return
    est = _estado()
    ups = telegram._api("getUpdates", data={"offset": est["ultimo_update"] + 1, "limit": 100})
    if not ups:
        print("Nenhuma mensagem nova.")
        return
    fila = carregar_fila()
    mudou = False
    for u in ups:
        est["ultimo_update"] = max(est["ultimo_update"], u["update_id"])
        # toque no botão "✅ Aprovar" (callback) ou texto "ok <id>"
        cq = u.get("callback_query")
        if cq:
            origem = str(((cq.get("message") or {}).get("chat") or {}).get("id"))
            if origem != chat:
                continue
            dado = cq.get("data") or ""
            oid = dado[3:] if dado.startswith("ok:") else None
            try:
                telegram._api("answerCallbackQuery", data={"callback_query_id": cq["id"]})
            except Exception:
                pass
        else:
            msg = u.get("message") or {}
            # só o seu chat privado manda comando; qualquer outro é ignorado
            if str((msg.get("chat") or {}).get("id")) != chat:
                continue
            alvo = direct_telegram.do_alerta((msg.get("reply_to_message") or {}).get("text"))
            if alvo and (msg.get("text") or "").strip():   # resposta a um alerta de direct → vai pro Instagram
                ok, aviso = direct_telegram.encaminhar(*alvo, msg["text"].strip())
                _responder(chat, aviso)
                print(f"📩 Direct pelo Telegram ({alvo[0]}): {'ok' if ok else aviso}")
                continue
            m = RE_OK.match(msg.get("text") or "")
            if not m:
                continue
            oid = m.group(1)
        if not oid:
            continue
        oferta = fila["ofertas"].get(oid)
        if not oferta:
            _responder(chat, f"❓ Não achei a oferta {oid} na fila. Confira o número e mande de novo.")
            continue
        oferta["aprovado_por_voce"] = agora().strftime("%d/%m/%Y %H:%M")
        oferta["preferencial"] = True   # entra na frente da fila do Instagram
        mudou = True
        _responder(chat, f"✅ Aprovado: {oferta.get('titulo', oid)}. A postagem no Instagram entra na próxima etapa.")
        print(f"✅ Aprovada: {oid} — {oferta.get('titulo', '')}")
    if mudou:
        salvar_fila(fila)
    _salvar_estado(est)
    try:   # confirma as lidas no Telegram (some da fila; senão o Worker, que só espia, tocaria de novo)
        telegram._api("getUpdates", data={"offset": est["ultimo_update"] + 1, "limit": 1, "timeout": 0})
    except Exception as e:
        print(f"⚠️  Não consegui confirmar as mensagens lidas no Telegram: {e}")


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
