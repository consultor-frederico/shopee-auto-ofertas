"""Seguidores de cada canal no Status do robô: quanto tem hoje e se cresceu ou caiu.

Mede (só leitura, com os segredos que o robô já usa):
  - Instagram @garimpovip4 e @ananovoachados (IG_ACCESS_TOKEN / IG_ACCESS_TOKEN_ANA);
  - Página do Facebook (FB_PAGE_ID + FB_PAGE_TOKEN);
  - Canal do Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID; o bot é admin do canal);
  - YouTube @garimpoVIP4 (YT_*; número público do canal, que o YouTube arredonda acima de 1.000).
O Canal do WhatsApp não tem API: fica de fora.

Guarda uma medição por dia em data/seguidores.json (o workflow 22 salva no repositório) e compara
com a medição anterior e com a de 7 dias atrás.

Teste: python -m src.seguidores
"""
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import facebook, metricas, youtube

BRT = timezone(timedelta(hours=-3))
ARQ = Path(__file__).resolve().parent.parent / "data" / "seguidores.json"
DIAS_GUARDADOS = 400


def _instagram(segredo):
    token = os.getenv(segredo, "").strip()
    if not token:
        return None
    return metricas._get(token, "me", {"fields": "followers_count"}).get("followers_count")


def _facebook():
    if not facebook.configurado():
        return None
    p = facebook._req("GET", facebook._env("FB_PAGE_ID"), params={"fields": "followers_count,fan_count"})
    return p.get("followers_count", p.get("fan_count"))


def _telegram():
    token, canal = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not canal:
        return None
    r = requests.get(f"https://api.telegram.org/bot{token}/getChatMemberCount",
                     params={"chat_id": canal}, timeout=30).json()
    if not r.get("ok"):
        raise RuntimeError(r.get("description", "?"))
    return r["result"]


def _youtube():
    """Lê o canal Garimpo VIP pelo id (dado público): funciona mesmo se o token for de outra conta."""
    if not youtube.configurado():
        return None
    r = requests.get("https://www.googleapis.com/youtube/v3/channels",
                     params={"part": "statistics", "id": youtube.CANAL_ID},
                     headers={"Authorization": f"Bearer {youtube._token()}"}, timeout=30)
    itens = r.json().get("items", []) if r.status_code == 200 else []
    if not itens:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:150]}")
    est = itens[0]["statistics"]
    if est.get("hiddenSubscriberCount"):
        raise RuntimeError("o canal esconde o número de inscritos")
    return int(est["subscriberCount"])


# chave → (nome na mensagem, função)
CANAIS = {
    "ig_garimpo": ("Instagram @garimpovip4", lambda: _instagram("IG_ACCESS_TOKEN")),
    "ig_ana": ("Instagram @ananovoachados", lambda: _instagram("IG_ACCESS_TOKEN_ANA")),
    "facebook": ("Facebook Garimpo VIP", _facebook),
    "telegram": ("Telegram garimpovipofertas", _telegram),
    "youtube": ("YouTube @garimpoVIP4", _youtube),
}


def _historico():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except Exception:
        return []


def _num(n):
    return f"{n:,}".replace(",", ".")


def _variacao(atual, antes):
    if antes is None:
        return None
    d = atual - antes
    return "sem mudança" if d == 0 else f"{'📈' if d > 0 else '📉'} {d:+d}"


def _anterior(historico, chave, hoje):
    """Última medição de um dia anterior a hoje, e a de 7 dias atrás (ou a mais próxima antes disso)."""
    antes = [h for h in historico if h["data"] < hoje and h.get("contas", {}).get(chave) is not None]
    ultima = antes[-1] if antes else None
    limite = (datetime.fromisoformat(hoje) - timedelta(days=7)).date().isoformat()
    semana = [h for h in antes if h["data"] <= limite]
    return ultima, (semana[-1] if semana else None)


def medir():
    """Devolve {chave: número} e {chave: erro}."""
    numeros, erros = {}, {}
    for chave, (nome, func) in CANAIS.items():
        try:
            n = func()
        except Exception as e:
            erros[chave] = str(e)
            print(f"::warning::Seguidores {nome}: {e}")
            continue
        if n is not None:
            numeros[chave] = int(n)
    return numeros, erros


def linhas_status(salvar=True):
    """Bloco do Status do robô. Salva a medição do dia em data/seguidores.json."""
    hoje = datetime.now(BRT).date().isoformat()
    historico = _historico()
    numeros, erros = medir()
    saida = ["👥 <b>Seguidores</b> (vs última medição • 7 dias)"]
    for chave, (nome, _) in CANAIS.items():
        if chave in erros:
            saida.append(f"• {nome}: sem dado ({html.escape(erros[chave])[:120]})")
            continue
        if chave not in numeros:
            continue   # segredo não configurado
        atual = numeros[chave]
        ultima, semana = _anterior(historico, chave, hoje)
        partes = []
        v = _variacao(atual, ultima["contas"][chave] if ultima else None)
        if v:
            partes.append(f"{v} desde {ultima['data'][8:10]}/{ultima['data'][5:7]}")
        v7 = _variacao(atual, semana["contas"][chave] if semana else None)
        if v7:
            partes.append(f"{v7} em 7 dias")
        extra = f" ({' • '.join(partes)})" if partes else " (primeira medição)"
        saida.append(f"• {nome}: <b>{_num(atual)}</b>{extra}")
    saida.append("• Canal do WhatsApp: o WhatsApp não deixa ler pelo robô (ver no celular)")
    if salvar and numeros:
        do_dia = next((h["contas"] for h in historico if h["data"] == hoje), {})
        historico = [h for h in historico if h["data"] != hoje]   # fica só a última medição de cada dia
        historico.append({"data": hoje, "hora": datetime.now(BRT).strftime("%H:%M"), "contas": {**do_dia, **numeros}})
        historico = historico[-DIAS_GUARDADOS:]
        try:
            ARQ.parent.mkdir(parents=True, exist_ok=True)
            ARQ.write_text(json.dumps(historico, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            print(f"::warning::Não consegui salvar {ARQ.name}: {e}")
    return saida


if __name__ == "__main__":
    print("\n".join(linhas_status(salvar=False)))
