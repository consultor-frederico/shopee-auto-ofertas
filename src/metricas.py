"""Medição do Instagram (@garimpovip4 e @ananovoachados): só LÊ dados, nunca posta.

Para cada conta, mede:
  - seguidores e número de posts (perfil);
  - alcance e visitas ao perfil dos últimos 7 dias (insights da conta);
  - alcance, salvamentos, compartilhamentos e interações dos últimos posts.

Manda um resumo no seu Telegram privado (TELEGRAM_CHAT_PRIVADO) e mostra no log o que cada
métrica respondeu, para sabermos o que o token consegue ler.

Teste: python -m src.metricas   (sem TELEGRAM_CHAT_PRIVADO, só mostra o resumo no log)
"""
import html
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import telegram

BRT = timezone(timedelta(hours=-3))
VERSAO = os.getenv("IG_API_VERSION", "v23.0")
API = f"https://graph.instagram.com/{VERSAO}"
ARQ_HISTORICO = Path(__file__).resolve().parent.parent / "data" / "metricas.json"

CONTAS = [
    ("@garimpovip4", "IG_ACCESS_TOKEN"),
    ("@ananovoachados", "IG_ACCESS_TOKEN_ANA"),
]
METRICAS_CONTA = ["reach", "profile_views"]
METRICAS_POST = ["reach", "saved", "shares", "total_interactions"]
POSTS_MEDIDOS = int(os.getenv("METRICAS_POSTS", "10"))


def _get(token, caminho, params=None):
    r = requests.get(f"{API}/{caminho}", params=params, timeout=60,
                     headers={"Authorization": f"Bearer {token}"})
    try:
        corpo = r.json()
    except ValueError:
        raise RuntimeError(f"HTTP {r.status_code} sem resposta válida")
    if r.status_code >= 400 or "error" in corpo:
        erro = corpo.get("error", {})
        raise RuntimeError(f"HTTP {r.status_code}: {str(erro.get('message', '?'))[:160]} "
                           f"(code {erro.get('code')}, subcode {erro.get('error_subcode')})")
    return corpo


def _soma_insight(corpo):
    """Soma os valores diários de uma métrica de conta."""
    total = 0
    for item in corpo.get("data") or []:
        for v in item.get("values") or []:
            total += v.get("value") or 0
    return total


def insights_conta(token, agora):
    """Alcance e visitas ao perfil dos últimos 7 dias. Cada métrica é tentada à parte."""
    resultado, erros = {}, {}
    since = int((agora - timedelta(days=7)).timestamp())
    until = int(agora.timestamp())
    for m in METRICAS_CONTA:
        try:
            corpo = _get(token, "me/insights", {"metric": m, "period": "day", "since": since, "until": until})
            resultado[m] = _soma_insight(corpo)
        except Exception as e:
            erros[m] = str(e)
    return resultado, erros


def toques_link(token, inicio, fim):
    """Toques nos links da bio (profile_links_taps) entre dois datetimes."""
    corpo = _get(token, "me/insights", {"metric": "profile_links_taps", "period": "day", "metric_type": "total_value",
                                         "since": int(inicio.timestamp()), "until": int(fim.timestamp())})
    return sum(((d.get("total_value") or {}).get("value") or 0) for d in corpo.get("data") or [])


def insights_post(token, media_id):
    """Métricas de um post. Se a lista completa falhar, tenta só as básicas."""
    for lista in (METRICAS_POST, ["reach", "saved"]):
        try:
            corpo = _get(token, f"{media_id}/insights", {"metric": ",".join(lista)})
            return {d["name"]: (d.get("values") or [{}])[0].get("value", 0) for d in corpo.get("data") or []}, None
        except Exception as e:
            ultimo = str(e)
    return {}, ultimo


def medir(arroba, token):
    agora = datetime.now(timezone.utc)
    perfil = _get(token, "me", {"fields": "user_id,username,followers_count,media_count"})
    s = {"conta": arroba, "usuario": perfil.get("username"), "data": agora.astimezone(BRT).isoformat(timespec="minutes"),
         "seguidores": perfil.get("followers_count"), "posts": perfil.get("media_count")}
    s["alcance_7d"], s["visitas_perfil_7d"] = None, None
    conta, erros = insights_conta(token, agora)
    s["alcance_7d"] = conta.get("reach")
    s["visitas_perfil_7d"] = conta.get("profile_views")
    s["erros_conta"] = erros
    midias = _get(token, "me/media", {"fields": "id,timestamp,media_type,like_count,comments_count,caption",
                                      "limit": POSTS_MEDIDOS}).get("data") or []
    posts, erros_post = [], []
    for m in midias:
        ins, erro = insights_post(token, m["id"])
        posts.append({
            "data": m.get("timestamp", "")[:10],
            "tipo": m.get("media_type"),
            "inicio": (m.get("caption") or "").strip()[:40],
            "curtidas": m.get("like_count"),
            "comentarios": m.get("comments_count"),
            "alcance": ins.get("reach"),
            "salvos": ins.get("saved"),
            "compartilhamentos": ins.get("shares"),
            "interacoes": ins.get("total_interactions"),
        })
        if erro:
            erros_post.append(erro)
        time.sleep(0.5)
    s["ultimos_posts"] = posts
    s["erros_post"] = sorted(set(erros_post))[:3]
    return s


def _historico():
    try:
        return json.loads(ARQ_HISTORICO.read_text(encoding="utf-8"))
    except Exception:
        return []


def _crescimento(atual, anterior):
    if not anterior or not atual or anterior.get("seguidores") in (None, 0):
        return ""
    pct = (atual["seguidores"] - anterior["seguidores"]) / anterior["seguidores"] * 100
    return f" ({pct:+.1f}% vs {anterior['data'][:10]})"


def resumo(s, anterior):
    linhas = [f"<b>{s['conta']}</b>",
              f"👥 {s['seguidores']} seguidores{_crescimento(s, anterior)}",
              f"👁 alcance 7 dias: {s['alcance_7d'] if s['alcance_7d'] is not None else 'sem dado'} • "
              f"visitas ao perfil: {s['visitas_perfil_7d'] if s['visitas_perfil_7d'] is not None else 'sem dado'}"]
    if s["ultimos_posts"]:
        linhas.append("🧾 últimos posts (alcance • salvos • compartilhou):")
        for p in s["ultimos_posts"][:5]:
            linhas.append(f"  {p['data'][5:]} {p['alcance'] if p['alcance'] is not None else '?'} • "
                          f"{p['salvos'] if p['salvos'] is not None else '?'} • "
                          f"{p['compartilhamentos'] if p['compartilhamentos'] is not None else '?'} "
                          f"<i>{html.escape(p['inicio'])}</i>")
    if s["erros_conta"] or s["erros_post"]:
        todos = list(s["erros_conta"].values()) + s["erros_post"]
        linhas.append("⚠️ não consegui ler: " + html.escape(" | ".join(todos))[:400])
    return "\n".join(linhas)


def rodar():
    historico = _historico()
    blocos, medidos = [], []
    for arroba, segredo in CONTAS:
        token = os.getenv(segredo, "").strip()
        if not token:
            blocos.append(f"⏸️ <b>{arroba}</b>: segredo {segredo} não configurado")
            continue
        try:
            s = medir(arroba, token)
        except Exception as e:
            blocos.append(f"❌ <b>{arroba}</b>: {html.escape(str(e))[:300]}")
            continue
        anteriores = [h for h in historico if h["conta"] == arroba]
        blocos.append(resumo(s, anteriores[-1] if anteriores else None))
        historico.append(s)
        medidos.append(s)
    texto = "📊 <b>Medição do Instagram</b>\n\n" + "\n\n".join(blocos)
    if POSTS_MEDIDOS > 10:   # medição longa: no log, todos os posts e a média de alcance por formato
        for s in medidos:
            print(f"\n{s['conta']}: {len(s['ultimos_posts'])} posts")
            por_tipo = {}
            for p in s["ultimos_posts"]:
                print(f"  {p['data']} {p['tipo']:<14} alcance {p['alcance']} • salvos {p['salvos']} • "
                      f"compart. {p['compartilhamentos']} • coment. {p['comentarios']}  {p['inicio']}")
                if p["alcance"] is not None:
                    por_tipo.setdefault(p["tipo"], []).append(p["alcance"])
            for tipo, v in por_tipo.items():
                print(f"  ➜ {tipo}: {len(v)} posts, alcance médio {sum(v) / len(v):.0f}, maior {max(v)}")
    print(texto.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    try:
        ARQ_HISTORICO.parent.mkdir(parents=True, exist_ok=True)
        ARQ_HISTORICO.write_text(json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"::warning::Não consegui salvar o histórico: {e}")
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if chat and os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
        telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "parse_mode": "HTML",
                                           "disable_web_page_preview": "true"})


if __name__ == "__main__":
    rodar()
