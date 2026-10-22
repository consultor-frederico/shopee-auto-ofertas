"""Perfis parecidos (contas profissionais públicas), lidos pela API do Instagram.

Lista em data/concorrentes.json, ex.: ["usuario1", "usuario2"]. Mostra seguidores e número de
posts de cada um. Usa o token do Garimpo VIP: a API só lê contas públicas profissionais
(contas pessoais ou privadas aparecem como "sem dado").
"""
import json
import os
from pathlib import Path

from . import metricas

ARQ = Path(__file__).resolve().parent.parent / "data" / "concorrentes.json"


def lista():
    try:
        dados = json.loads(ARQ.read_text(encoding="utf-8"))
        return [str(u).lstrip("@").strip() for u in dados if str(u).strip()]
    except Exception:
        return []


def _sinais(midias):
    """Sinais de automação (heurística): posts no mesmo minuto, legendas repetidas, formato."""
    from collections import Counter
    from datetime import datetime, timedelta, timezone
    if not midias:
        return "sem posts recentes"
    brt = timezone(timedelta(hours=-3))
    agora = datetime.now(timezone.utc)
    recentes = [m for m in midias if datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")) >= agora - timedelta(days=30)]
    n = len(midias)
    minutos = Counter(datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")).astimezone(brt).strftime("%H:%M") for m in midias)
    mesmo_horario = max(minutos.values()) / n
    inicios = Counter((m.get("caption") or "").strip()[:25].lower() for m in midias if (m.get("caption") or "").strip())
    legenda_repetida = sum(c for c in inicios.values() if c > 1) / n
    formatos = Counter(m.get("media_type", "?") for m in midias)
    por_dia = len(recentes) / 30
    sinal = []
    if mesmo_horario >= 0.3:
        sinal.append("horário repetido")
    if legenda_repetida >= 0.5:
        sinal.append("legendas repetidas")
    veredito = "padrão de robô provável" if len(sinal) >= 2 else ("sinais parciais" if sinal else "sem sinal de robô")
    return (f"{por_dia:.1f} posts/dia (30d), {mesmo_horario:.0%} no mesmo horário, "
            f"{legenda_repetida:.0%} com legenda repetida, formatos {dict(formatos)} → {veredito}")


def linhas():
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    saida = []
    if not token:
        return saida
    for usuario in lista():
        try:
            campo = "business_discovery.username(%s){username,followers_count,media_count,media.limit(50){timestamp,caption,media_type}}" % usuario
            d = metricas._get(token, "me", {"fields": campo})["business_discovery"]
            midias = (d.get("media") or {}).get("data") or []
            saida.append(f"@{d.get('username', usuario)}: {d.get('followers_count', '?')} seguidores, "
                         f"{d.get('media_count', '?')} posts. {_sinais(midias)}")
        except Exception as e:
            saida.append(f"@{usuario}: sem dado ({str(e)[:100]})")
    return saida
