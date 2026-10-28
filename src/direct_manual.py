"""Mandar uma mensagem no direct de alguém, a pedido do Fred (workflow 24).

PARA = @ ou pedaço do nome (ex.: "thiago"). Procura nas conversas recentes da conta;
só manda se achar exatamente uma pessoa. Se achar nenhuma ou várias, lista no log e não manda.
Uso: PERFIL=garimpo PARA=thiago TEXTO="..." python -m src.direct_manual
"""
import os
import sys
import unicodedata

from .direct_telegram import ARROBAS, TOKENS, _req


def _norm(t):
    return unicodedata.normalize("NFD", (t or "").lower()).encode("ascii", "ignore").decode()


def rodar():
    perfil = os.getenv("PERFIL", "garimpo").strip() or "garimpo"
    para = _norm(os.getenv("PARA", "").strip().lstrip("@"))
    texto = os.getenv("TEXTO", "").strip()
    token = os.getenv(TOKENS[perfil], "").strip()
    conta = _req(token, "GET", "me", params={"fields": "user_id,username"})
    if (conta.get("username") or "").lower() != ARROBAS[perfil].lstrip("@"):
        sys.exit(f"::error::O token não é do {ARROBAS[perfil]}.")
    ig_id = str(conta.get("user_id") or conta.get("id"))
    conversas = _req(token, "GET", f"{ig_id}/conversations", params={
        "platform": "instagram", "limit": 50,
        "fields": "updated_time,participants,messages.limit(1){from,created_time,message}"}).get("data", [])
    pessoas = []
    for c in conversas:
        for p in (c.get("participants") or {}).get("data") or []:
            if str(p.get("id")) != ig_id:
                pessoas.append((p.get("username") or "", str(p.get("id")), c.get("updated_time", "")))
    print("Conversas recentes:", ", ".join(f"@{u} ({t[:16]})" for u, _, t in pessoas[:50]))
    achados = [p for p in pessoas if para and para in _norm(p[0])]
    if len(achados) != 1:
        sys.exit(f"::error::Achei {len(achados)} conversa(s) com '{para}': "
                 + (", ".join("@" + u for u, _, _ in achados) or "nenhuma") + ". Nada foi enviado.")
    usuario, autor, _ = achados[0]
    if not texto:
        print(f"::notice::Achei @{usuario} (sem TEXTO: nada enviado).")
        return
    _req(token, "POST", f"{ig_id}/messages", json={"recipient": {"id": autor}, "message": {"text": texto[:1000]}})
    print(f"::notice::✅ Enviado para @{usuario} pelo direct do {ARROBAS[perfil]}.")


if __name__ == "__main__":
    rodar()
