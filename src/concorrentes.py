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


def linhas():
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    saida = []
    if not token:
        return saida
    for usuario in lista():
        try:
            corpo = metricas._get(token, "me", {"fields": "business_discovery.username(%s){username,followers_count,media_count}" % usuario})
            d = corpo["business_discovery"]
            saida.append(f"@{d.get('username', usuario)}: {d.get('followers_count', '?')} seguidores, "
                         f"{d.get('media_count', '?')} posts")
        except Exception as e:
            saida.append(f"@{usuario}: sem dado ({str(e)[:100]})")
    return saida
