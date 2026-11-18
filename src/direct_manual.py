"""Mandar uma mensagem no direct de alguém, a pedido do Fred (workflow 24).

PARA = @ ou pedaço do nome (ex.: "thiago"). Procura nas conversas recentes da conta;
só manda se achar exatamente uma pessoa. Se achar nenhuma ou várias, lista no log e não manda.
Uso: PERFIL=garimpo PARA=thiago TEXTO="..." python -m src.direct_manual
"""
import os
import sys
import unicodedata

from . import cofre
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
    nomes = {}
    for _, pid, _ in pessoas[:30]:   # nome de exibição ("Tiago Souza"), além do @
        try:
            nomes[pid] = _req(token, "GET", pid, params={"fields": "name"}).get("name") or ""
        except Exception:
            nomes[pid] = ""
    print("Conversas recentes:", ", ".join(f"@{cofre.oculto(u)} ({t[:16]})" for u, i, t in pessoas[:50]))
    achados = [p for p in pessoas if para and (para in _norm(p[0]) or para in _norm(nomes.get(p[1])))]
    if len(achados) != 1:
        sys.exit(f"::error::Achei {len(achados)} conversa(s) com '{para}': "
                 + (", ".join("@" + u for u, _, _ in achados) or "nenhuma") + ". Nada foi enviado.")
    usuario, autor, _ = achados[0]
    if os.getenv("LER_FOTO", "").strip().lower() in ("1", "true", "sim"):
        ler_foto(token, ig_id, conversas, autor)
        return
    if not texto:
        print(f"::notice::Achei @{cofre.oculto(usuario)} (sem TEXTO: nada enviado).")
        return
    _req(token, "POST", f"{ig_id}/messages", json={"recipient": {"id": autor}, "message": {"text": texto[:1000]}})
    print(f"::notice::✅ Enviado para @{cofre.oculto(usuario)} pelo direct do {ARROBAS[perfil]}.")


PROMPT_PRINT = """Uma seguidora mandou esta foto no direct de uma página de achadinhos. Descreva SÓ o produto e o anúncio,
sem dados pessoais. Responda só com JSON:
{"tem_produto": true/false, "o_que_e": "produto em até 10 palavras", "marca": "", "modelo": "",
 "loja": "loja/app do print, se aparecer", "preco": "preço que aparece", "nota": "avaliação que aparece",
 "vendidos": "quantidade vendida que aparece", "vendedor": "nome do vendedor/loja oficial, se aparecer",
 "outros": "outros textos importantes do anúncio (frete, cupom, desconto, internacional), até 25 palavras"}"""


def ler_foto(token, ig_id, conversas, autor):
    """18/11/2026 (Vanessa): lê as últimas fotos que a pessoa mandou e descreve o produto no log (não manda nada)."""
    from . import foto_ze
    conv = next((c for c in conversas if any(str(p.get("id")) == autor
                                             for p in (c.get("participants") or {}).get("data") or [])), None)
    if not conv:
        sys.exit("::error::Conversa não encontrada.")
    msgs = _req(token, "GET", conv["id"], params={
        "fields": "messages.limit(15){id,created_time,from,message,attachments{image_data{url},file_url,mime_type}}"}
                ).get("messages", {}).get("data", [])
    fotos = 0
    for m in msgs:
        if str((m.get("from") or {}).get("id")) != autor:
            continue
        for a in (m.get("attachments") or {}).get("data") or []:
            url = (a.get("image_data") or {}).get("url") or a.get("file_url")
            if not url:
                continue
            fotos += 1
            try:
                dados, tipo = foto_ze._baixar(url)
                lido = foto_ze._gemini(PROMPT_PRINT, dados, tipo) or foto_ze._groq(PROMPT_PRINT, dados, tipo)
            except Exception as e:
                lido = f"erro: {e}"
            print(f"::notice::Foto {fotos} ({m.get('created_time', '')[:16]}): {lido}")
            if fotos >= 3:
                return
    if not fotos:
        print("::notice::Nenhuma foto da pessoa nas últimas 15 mensagens.")


if __name__ == "__main__":
    rodar()
