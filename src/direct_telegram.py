"""Responder um direct do Instagram pelo Telegram privado.

O alerta de "direct sem resposta" (src/busca_ze.py) termina com a linha "ref: <perfil>/<id da pessoa>".
Quando o Fred responde AQUELE alerta no Telegram (segurar a mensagem → Responder), o src.aprovacao
lê a resposta e chama encaminhar(): o texto vai para o direct da pessoa, na conta certa (Garimpo ou Ana).
O Instagram só deixa mandar até 24h depois da última mensagem da pessoa.
"""
import os
import re

import requests

from .instagram import API

RE_REF = re.compile(r"ref:\s*(garimpo|ana)/(\d+)")
TOKENS = {"garimpo": "IG_ACCESS_TOKEN", "ana": "IG_ACCESS_TOKEN_ANA"}
ARROBAS = {"garimpo": "@garimpovip4", "ana": "@ananovoachados"}


def ref(perfil, autor):
    return f"ref: {perfil}/{autor}"


def do_alerta(texto_alerta):
    """(perfil, id da pessoa) a partir do texto do alerta respondido, ou None."""
    m = RE_REF.search(texto_alerta or "")
    return (m.group(1), m.group(2)) if m else None


def _req(token, metodo, caminho, **kw):
    r = requests.request(metodo, f"{API}/{caminho}", timeout=60, headers={"Authorization": f"Bearer {token}"}, **kw)
    corpo = r.json()
    if r.status_code >= 400 or "error" in corpo:
        erro = corpo.get("error", corpo)
        raise RuntimeError(f"{erro.get('message', erro)} (code {erro.get('code')})")
    return corpo


def encaminhar(perfil, autor, texto):
    """Manda o texto no direct da pessoa. Devolve (ok, mensagem para o Fred)."""
    token = os.getenv(TOKENS[perfil], "").strip()
    if not token:
        return False, f"❌ Falta o segredo {TOKENS[perfil]}; não mandei."
    try:
        conta = _req(token, "GET", "me", params={"fields": "user_id,username"})
        if (conta.get("username") or "").lower() != ARROBAS[perfil].lstrip("@"):
            return False, f"❌ O token não é do {ARROBAS[perfil]}; não mandei."
        ig_id = str(conta.get("user_id") or conta.get("id"))
        _req(token, "POST", f"{ig_id}/messages", json={"recipient": {"id": autor}, "message": {"text": texto[:1000]}})
        return True, f"✅ Enviado no direct do {ARROBAS[perfil]}."
    except Exception as e:
        return False, (f"❌ Não consegui mandar: {str(e)[:200]}\n"
                       "(Se já passou de 24h da mensagem da pessoa, o Instagram não deixa mais.)")
