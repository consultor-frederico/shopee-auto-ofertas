"""Quem responde um story com "quero" (vira mensagem no direct) recebe o link daquele achado.

Vale para todas as contas (Garimpo VIP e Ana). Roda dentro do responder, antes da Busca do Zé.
"""
import json
from datetime import datetime, timedelta

from . import config
from .garimpar import BRT, FMT, agora, carregar_fila

ARQ = config.PASTA_PERFIL / "story_dms.json"
JANELA = timedelta(hours=23)     # story some em 24h e o Instagram só deixa responder até 24h
MAX_POR_RODADA = 20


def tratados():
    """Ids das mensagens do direct que já foram tratadas aqui (a Busca do Zé pula essas)."""
    if ARQ.exists():
        return set(json.loads(ARQ.read_text(encoding="utf-8")))
    return set()


def _salvar(ids):
    ARQ.write_text(json.dumps(sorted(ids)[-500:], ensure_ascii=False), encoding="utf-8")


def _hora(txt):
    """created_time da API ("2026-10-13T22:40:00+0000") no fuso de Brasília."""
    try:
        return datetime.strptime(txt, "%Y-%m-%dT%H:%M:%S%z").astimezone(BRT)
    except (ValueError, TypeError):
        return None


def _oferta_do_story(fila, story_id, quando):
    """O achado do story: pelo id do story; se não der, o último story publicado antes da mensagem."""
    com_story = [o for o in fila["ofertas"].values()
                 if o.get("status") == "postado" and o.get("story") == "ok" and o.get("link_afiliado")]
    if story_id:
        for o in com_story:
            if str(o.get("story_id")) == str(story_id):
                return o
    antes = [o for o in com_story
             if quando - JANELA <= datetime.strptime(o["postado_em"], FMT).replace(tzinfo=BRT) <= quando]
    return max(antes, key=lambda o: o["postado_em"]) if antes else None


def responder_stories(api, minha):
    from .responder import DM, DM_BOTAO, NOME_LOJA, TITULO_BOTAO, pediu_link
    ig_id = minha["user_id"]
    corpo = api._req("GET", f"{ig_id}/conversations", params={
        "platform": "instagram", "limit": 25,
        "fields": "id,messages.limit(3){id,message,from,created_time,story}"})
    feitos = tratados()
    fila = carregar_fila()
    enviados = 0
    for conv in corpo.get("data", []):
        msgs = (conv.get("messages") or {}).get("data") or []
        if not msgs:
            continue
        m = msgs[0]                                          # a mais nova
        autor = (m.get("from") or {}).get("id")
        reply = (m.get("story") or {}).get("reply_to")
        if autor == ig_id or m["id"] in feitos or not reply or not pediu_link(m.get("message") or ""):
            continue
        quando = _hora(m.get("created_time", ""))
        if not quando or agora() - quando > JANELA:
            continue
        if enviados >= MAX_POR_RODADA:
            break
        o = _oferta_do_story(fila, reply.get("id"), quando)
        feitos.add(m["id"])
        if not o:
            print("⚠️  Resposta de story sem achado correspondente; deixei sem resposta.")
            continue
        loja = NOME_LOJA.get(o.get("plataforma") or "shopee", "loja")
        try:
            try:
                api._req("POST", f"{ig_id}/messages", json={
                    "recipient": {"id": autor},
                    "message": {"attachment": {"type": "template", "payload": {
                        "template_type": "button", "text": DM_BOTAO.format(titulo=o["titulo"], loja=loja)[:640],
                        "buttons": [{"type": "web_url", "url": o["link_afiliado"], "title": TITULO_BOTAO}]}}}})
            except Exception as e:
                print(f"   (botão recusado: {e}; enviando como texto)")
                api._req("POST", f"{ig_id}/messages", json={
                    "recipient": {"id": autor},
                    "message": {"text": DM.format(titulo=o["titulo"], link=o["link_afiliado"])}})
            enviados += 1
            print(f"📲 Story: link enviado no direct — {o['titulo']}")
        except Exception as e:
            print(f"::warning::Story: não consegui mandar o link: {e}")
    _salvar(feitos)
    return enviados
