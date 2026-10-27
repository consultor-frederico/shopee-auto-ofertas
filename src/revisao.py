"""Revisão semanal do robô (toda sexta às 17h): confere se está tudo funcionando e manda o
resumo no Telegram privado do Fred (segredo TELEGRAM_CHAT_PRIVADO).

O que confere:
  1. Workflows de produção dos últimos 7 dias: quantas rodadas, quantas falharam e se algum
     parou de rodar.
  2. Se o código compila (todos os arquivos de src/).
  3. Instagram @garimpovip4: token válido, seguidores e quando saiu o último post.
  4. Fila: quantas ofertas estão esperando.

Teste: python -m src.revisao  (sem TELEGRAM_CHAT_PRIVADO, só mostra o resumo no log)
"""
import compileall
import html
import io
import json
import os
import contextlib
from datetime import datetime, timedelta, timezone

import requests

from . import config, metricas, telegram

DIAS = 7
BRT = timezone(timedelta(hours=-3))

# Workflows que precisam rodar toda semana (arquivo → nome amigável).
PRODUCAO = {
    "agenda.yml": "Relógio do robô",
    "responder.yml": "Responder EU QUERO",
    "garimpo.yml": "Garimpo de ofertas",
    "postar.yml": "Posts no Instagram",
    "telegram-ofertas.yml": "Ofertas no Telegram",
    "campanhas.yml": "Cupons e campanhas",
    "whatsapp.yml": "Kit do WhatsApp",
    "busca.yml": "Reels da Busca do Zé",
    "ze.yml": "Post do Zé Garimpo",
    # "limpeza.yml" desligada em 12/10/2026 (posts antigos ficam no ar)
    "chamada.yml": "Chamada do Telegram",
    "token.yml": "Renovar token",
}


def _gh(caminho, params=None):
    r = requests.get(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/{caminho}",
                     params=params, timeout=60,
                     headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                              "Accept": "application/vnd.github+json"})
    r.raise_for_status()
    return r.json()


def checar_workflows():
    """Consulta cada rotina pelo arquivo (não pela lista geral, que é longa e pode vir incompleta)."""
    corte = datetime.now(timezone.utc) - timedelta(days=DIAS)
    por_wf = {}
    for arq, nome in PRODUCAO.items():
        runs, pagina = [], 1
        while pagina <= 30:   # rotinas que rodam a cada 15 min: várias páginas por semana
            lote = _gh(f"actions/workflows/{arq}/runs", {"per_page": 100, "page": pagina}).get("workflow_runs", [])
            runs += [r for r in lote if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= corte]
            antigas = [r for r in lote if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) < corte]
            if len(lote) < 100 or antigas:
                break
            pagina += 1
        d = {"total": len(runs), "falhas": 0, "ultima_falha": None}
        for r in runs:
            if r.get("conclusion") in ("failure", "timed_out", "startup_failure"):
                d["falhas"] += 1
                d["ultima_falha"] = max(d["ultima_falha"] or "", r["created_at"])
        por_wf[arq] = d
    problemas, ok = [], 0
    for arq, nome in PRODUCAO.items():
        d = por_wf[arq]
        if d["total"] == 0:
            problemas.append(f"⛔ <b>{nome}</b>: não rodou nenhuma vez na semana")
        elif d["falhas"]:
            quando = datetime.fromisoformat(d["ultima_falha"].replace("Z", "+00:00")).astimezone(BRT)
            problemas.append(f"❌ <b>{nome}</b>: {d['falhas']} falha(s) em {d['total']} rodadas "
                             f"(última {quando:%d/%m %H:%M})")
        else:
            ok += 1
    return problemas, ok, sum(d["total"] for d in por_wf.values())


def checar_codigo():
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        bom = compileall.compile_dir("src", quiet=1, force=True)
    return bom, saida.getvalue().strip()[-500:]


def checar_instagram(arroba, segredo):
    token = os.getenv(segredo, "").strip()
    if not token:
        return False, f"⏸️ {arroba}: segredo {segredo} não configurado"
    try:
        c = metricas._get(token, "me", {"fields": "username,followers_count,media_count"})
        midias = metricas._get(token, "me/media", {"fields": "timestamp", "limit": 1}).get("data") or []
    except Exception as e:
        return False, f"❌ {arroba} com problema: {html.escape(str(e))[:300]}"
    texto = (f"@{c.get('username')}: {c.get('followers_count', '?')} seguidores, "
             f"{c.get('media_count', '?')} posts")
    if not midias:
        return False, f"⚠️ {texto} — nenhum post encontrado"
    ultimo = datetime.strptime(midias[0]["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(BRT)
    horas = (datetime.now(BRT) - ultimo).total_seconds() / 3600
    linha = f"{texto}; último post {ultimo:%d/%m %H:%M}"
    if horas > 24:
        return False, f"⚠️ {linha} — mais de 24h sem postar"
    return True, f"✅ {linha}"


def checar_fila():
    try:
        fila = json.loads(config.ARQ_FILA.read_text(encoding="utf-8"))["ofertas"]
    except Exception as e:
        return False, f"❌ Não consegui ler a fila: {html.escape(str(e))[:200]}"
    pend = sum(1 for o in fila.values() if o.get("status") == "pendente")
    if pend < 10:
        return False, f"⚠️ Fila quase vazia: {pend} ofertas esperando"
    return True, f"✅ Fila: {pend} ofertas esperando"


def montar():
    linhas = [f"🩺 <b>Status do robô (Garimpo VIP e Ana)</b> — {datetime.now(BRT):%d/%m/%Y %H:%M}", ""]
    tudo_ok = True
    try:
        problemas, ok, total = checar_workflows()
        if problemas:
            tudo_ok = False
            linhas += ["<b>Robô (GitHub):</b>"] + problemas + [f"✅ outras {ok} rotinas sem falhas ({total} rodadas na semana)"]
        else:
            linhas.append(f"✅ Robô: todas as {ok} rotinas rodaram sem falhas ({total} rodadas na semana)")
    except Exception as e:
        tudo_ok = False
        linhas.append(f"❌ Não consegui ler as rodadas do GitHub: {html.escape(str(e))[:200]}")
    bom, erro = checar_codigo()
    tudo_ok &= bool(bom)
    linhas.append("✅ Código compila sem erros" if bom else f"❌ Código com erro:\n<code>{html.escape(erro)}</code>")
    for arroba, segredo in metricas.CONTAS:
        ok_parte, linha = checar_instagram(arroba, segredo)
        tudo_ok &= ok_parte
        linhas.append(linha)
    # "Perfis parecidos" saiu do status em 27/10/2026 a pedido do Fred.
    for ok_parte, linha in (checar_fila(),):
        tudo_ok &= ok_parte
        linhas.append(linha)
    linhas += ["", "👍 Tudo certo, pode deixar rodar." if tudo_ok else "👀 Tem coisa para olhar — abre uma conversa com o Claude e cola esta mensagem."]
    return "\n".join(linhas)


def main():
    texto = montar()
    print(texto)
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if not chat or not os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        print("::warning::Faltam TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_PRIVADO — resumo só no log.")
        return
    telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "parse_mode": "HTML",
                                       "disable_web_page_preview": "true"})
    print("📨 Enviado no Telegram privado.")


if __name__ == "__main__":
    main()
