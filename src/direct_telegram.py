"""Responder um direct do Instagram pelo Telegram privado.

1) Alerta respondido: o alerta de "direct sem resposta" (src/busca_ze.py) termina com a linha "ref: <perfil>/<id>".
   Quando o Fred responde AQUELE alerta no Telegram (segurar a mensagem → Responder), o src.aprovacao
   chama encaminhar(): o texto vai para o direct da pessoa, na conta certa (Garimpo ou Ana).
2) Comando (19/11/2026, pedido do Fred: "eu peço pra você responder por lá"), sem esperar alerta:
   - "/ze vanessa Oi Vanessa, ..."  → manda o texto do jeito que está (/ana = pelo direct da Ana).
   - "responde a Vanessa dizendo que não achei robô confiável" (ou começando com "zé", "fala", "diz", "avisa",
     "manda"...) → a IA escreve no jeito do Zé, lendo a conversa, e mostra o RASCUNHO com o botão ✅ Enviar.
     Responder o rascunho com outro texto manda o texto do Fred no lugar.
O Instagram só deixa mandar até 24h depois da última mensagem da pessoa. Passou disso, tenta como
"atendimento humano" (vale até 7 dias, se a Meta liberar) e, se não der, avisa no Telegram.
Nada da conversa é gravado no repositório (que é público): o rascunho fica só na mensagem do Telegram.
"""
import json
import os
import re
import unicodedata
from datetime import datetime, timezone

import requests

from . import cofre
from .instagram import API

RE_REF = re.compile(r"ref:\s*(garimpo|ana)/(\d+)")
TOKENS = {"garimpo": "IG_ACCESS_TOKEN", "ana": "IG_ACCESS_TOKEN_ANA"}
ARROBAS = {"garimpo": "@garimpovip4", "ana": "@ananovoachados"}
RE_COMANDO = re.compile(r"^\s*/(ze|zé|ana)(?:@\w+)?\s+@?([\w.]+)[\s,:]+(.+)$", re.I | re.S)
RE_PEDIDO = re.compile(r"^\s*(z[eé]\b|responde|responda|respondi?\b|fala|fale|diz\b|diga|avisa|avise|manda|mande"
                       r"|escreve|escreva|pergunta|pergunte)", re.I)
INICIO_RASCUNHO, FIM_RASCUNHO = "▼▼▼", "▲▲▲"
BOTOES_RASCUNHO = json.dumps({"inline_keyboard": [[{"text": "✅ Enviar", "callback_data": "dm:ok"},
                                                    {"text": "❌ Cancelar", "callback_data": "dm:x"}]]})


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


def _norm(t):
    return unicodedata.normalize("NFD", (t or "").lower()).encode("ascii", "ignore").decode()


def _conta(perfil):
    """(token, id da conta) conferindo que o token é mesmo da conta certa."""
    token = os.getenv(TOKENS[perfil], "").strip()
    if not token:
        raise ValueError(f"Falta o segredo {TOKENS[perfil]}")
    conta = _req(token, "GET", "me", params={"fields": "user_id,username"})
    if (conta.get("username") or "").lower() != ARROBAS[perfil].lstrip("@"):
        raise ValueError(f"O token não é do {ARROBAS[perfil]}")
    return token, str(conta.get("user_id") or conta.get("id"))


def _horas(txt):
    """Horas desde '2026-10-10T12:09:48+0000' (None se não der para ler)."""
    try:
        quando = datetime.strptime(txt[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) - quando).total_seconds() / 3600


def conversas(token, ig_id, n_msgs=8):
    """Conversas recentes: [{usuario, autor, msgs (mais recente primeiro), horas (desde a última msg DA PESSOA)}]."""
    dados = _req(token, "GET", f"{ig_id}/conversations", params={
        "platform": "instagram", "limit": 50,
        "fields": f"updated_time,participants,messages.limit({n_msgs}){{from,created_time,message}}"}).get("data", [])
    pessoas = []
    for c in dados:
        msgs = (c.get("messages") or {}).get("data") or []
        for p in (c.get("participants") or {}).get("data") or []:
            if str(p.get("id")) == ig_id:
                continue
            autor = str(p.get("id"))
            dela = [m for m in msgs if str((m.get("from") or {}).get("id")) == autor]
            pessoas.append({"usuario": p.get("username") or "", "autor": autor, "msgs": msgs,
                            "horas": _horas(dela[0].get("created_time")) if dela else None, "conv": c.get("id")})
    return pessoas


def achar(token, ig_id, para, pessoas=None):
    """A pessoa com '@' ou pedaço do nome PARA. Devolve (pessoa, lista de parecidas)."""
    pessoas = conversas(token, ig_id) if pessoas is None else pessoas
    alvo = _norm(para.lstrip("@"))
    if not alvo:
        return None, []
    exato = [p for p in pessoas if _norm(p["usuario"]) == alvo]
    if len(exato) == 1:
        return exato[0], exato
    achados = [p for p in pessoas if alvo in _norm(p["usuario"])]
    if not achados:   # nome de exibição ("Vanessa Lima"), além do @
        for p in pessoas[:30]:
            try:
                p["nome"] = _req(token, "GET", p["autor"], params={"fields": "name"}).get("name") or ""
            except Exception:
                p["nome"] = ""
        achados = [p for p in pessoas if alvo in _norm(p.get("nome"))]
    return (achados[0] if len(achados) == 1 else None), achados


def mandar(token, ig_id, autor, texto):
    """Manda no direct. Fora das 24h tenta como atendimento humano (até 7 dias). Levanta erro se não der."""
    corpo = {"recipient": {"id": autor}, "message": {"text": texto[:1000]}}
    try:
        _req(token, "POST", f"{ig_id}/messages", json=corpo)
        return
    except RuntimeError as e:
        primeiro = e
    try:   # fora da janela de 24h: a Meta aceita resposta de pessoa de verdade até 7 dias (se a conta tiver a permissão)
        _req(token, "POST", f"{ig_id}/messages", json={**corpo, "messaging_type": "MESSAGE_TAG", "tag": "HUMAN_AGENT"})
    except RuntimeError:
        raise primeiro


def _janela(horas):
    if horas is None:
        return ""
    if horas > 24 * 7:
        return f"⚠️ A última mensagem dela(e) foi há {horas / 24:.0f} dias: o Instagram não deixa mais responder."
    if horas > 24:
        return (f"⚠️ A última mensagem dela(e) foi há {horas:.0f}h (passou das 24h). Vou tentar mesmo assim como "
                "atendimento humano; se o Instagram recusar, eu aviso.")
    return ""


def encaminhar(perfil, autor, texto):
    """Manda o texto no direct da pessoa. Devolve (ok, mensagem para o Fred)."""
    try:
        token, ig_id = _conta(perfil)
        mandar(token, ig_id, autor, texto)
        return True, f"✅ Enviado no direct do {ARROBAS[perfil]}."
    except Exception as e:
        return False, (f"❌ Não consegui mandar: {str(e)[:200]}\n"
                       "(Se já passou de 24h da mensagem da pessoa, o Instagram não deixa mais.)")


# ---------- comando no Telegram ----------

AJUDA = ("Para o Zé responder alguém no direct:\n\n"
         "1) Texto pronto (vai do jeito que você escrever):\n/ze vanessa Oi Vanessa! ...\n\n"
         "2) Você diz o que quer e o Zé escreve (mostro o rascunho antes):\n"
         "responde a Vanessa dizendo que não achei robô aspirador de vendedor confiável\n\n"
         "Use o @ ou um pedaço do nome. /ana no lugar de /ze manda pelo direct da Ana.")

PROMPT_PEDIDO = """O dono de uma página de achadinhos no Instagram mandou este pedido para o robô dele:
"{pedido}"
Diga para quem é a mensagem e o que ela deve dizer. Responda só com JSON:
{{"para": "@ ou nome da pessoa, como ele escreveu (sem 'a', 'o', 'pra')", "perfil": "ana se ele pediu pelo perfil/direct da Ana, senão garimpo",
 "instrucao": "o que a mensagem deve dizer, com todos os detalhes que ele deu"}}"""

PROMPT_ZE = """Você é o Zé Garimpo, que responde o direct do Instagram {arroba}, uma página de achadinhos
(indica produtos da Shopee, Mercado Livre, AliExpress e lojas oficiais com link de afiliado; a pessoa paga o mesmo preço).
O dono da página pediu para você mandar esta mensagem para @{usuario}:
"{instrucao}"

Conversa até agora (mais antiga primeiro):
{conversa}

Escreva a mensagem do Zé seguindo FIELMENTE o que o dono pediu: curta (até 4 frases), simpática, em português do
Brasil, jeito de garimpeiro bem-humorado, começando com "Oi! 🤠" (ou "Oi, <primeiro nome>! 🤠").
NUNCA prometa frete grátis, desconto, prazo, estoque nem aviso futuro que o dono não pediu. Não invente produto, preço ou link.
Responda só com JSON {{"resposta": "<texto da mensagem>"}}."""


def _groq_json(prompt):
    from . import config
    from .legenda import _chamar_groq
    if not config.GROQ_API_KEY:
        raise ValueError("falta o segredo GROQ_API_KEY no workflow 22")
    r = _chamar_groq(prompt) or ""
    return json.loads(re.search(r"\{.*\}", r, re.S).group(0))


def _seguro(resposta, pedido):
    """Sem link/@/telefone/pix inventado pela IA (o que o próprio Fred escreveu pode)."""
    from .busca_ze import _resposta_segura
    limpo = resposta
    for pedaco in re.findall(r"\S+", pedido or ""):
        if re.search(r"[@/.]|\d{4}", pedaco):
            limpo = limpo.replace(pedaco.strip(".,;!?"), "")
    return _resposta_segura(limpo)


def _texto_conversa(p, ig_id):
    linhas = []
    for m in reversed(p["msgs"]):
        txt = (m.get("message") or "").strip()
        if txt:
            quem = "Página" if str((m.get("from") or {}).get("id")) == ig_id else "Cliente"
            linhas.append(f"{quem}: {txt[:300]}")
    return "\n".join(linhas[-8:]) or "(sem texto)"


def _nao_achei(para, achados):
    if achados:
        return (f"❓ Achei {len(achados)} conversas com \"{para}\": "
                + ", ".join("@" + a["usuario"] for a in achados[:8]) + ". Mande de novo com o @ certo.")
    return (f"❓ Não achei \"{para}\" nas conversas recentes do direct. Confira o @ (a pessoa precisa ter "
            "mandado mensagem antes).")


def eh_comando(texto):
    t = (texto or "").strip()
    return bool(RE_COMANDO.match(t)) or bool(RE_PEDIDO.match(t)) or t.lower() in ("/ze", "/zé", "/ana", "/ajuda")


def comando(texto):
    """Pedido do Fred no Telegram. Devolve (resposta, teclado ou None)."""
    t = (texto or "").strip()
    if t.lower() in ("/ze", "/zé", "/ana", "/ajuda"):
        return AJUDA, None
    m = RE_COMANDO.match(t)
    try:
        if m:   # texto pronto: manda já
            perfil = "ana" if m.group(1).lower() == "ana" else "garimpo"
            token, ig_id = _conta(perfil)
            p, achados = achar(token, ig_id, m.group(2))
            if not p:
                return _nao_achei(m.group(2), achados), None
            aviso = _janela(p["horas"])
            if p["horas"] is not None and p["horas"] > 24 * 7:
                return aviso + "\nNada foi enviado.", None
            mandar(token, ig_id, p["autor"], m.group(3).strip())
            print(f"📩 /ze: enviado para @{cofre.oculto(p['usuario'])} ({perfil})")
            return f"✅ Enviado para @{p['usuario']} no direct do {ARROBAS[perfil]}.", None
        # pedido em palavras: a IA entende para quem e escreve no jeito do Zé
        ped = _groq_json(PROMPT_PEDIDO.format(pedido=t[:800]))
        para = str(ped.get("para") or "").strip()
        perfil = "ana" if str(ped.get("perfil", "")).lower() == "ana" else "garimpo"
        instrucao = str(ped.get("instrucao") or t).strip()
        if not para:
            return "❓ Não entendi para quem é a mensagem.\n\n" + AJUDA, None
        token, ig_id = _conta(perfil)
        p, achados = achar(token, ig_id, para)
        if not p:
            return _nao_achei(para, achados), None
        if p["horas"] is not None and p["horas"] > 24 * 7:
            return _janela(p["horas"]) + "\nNada foi escrito.", None
        arroba = ARROBAS[perfil]
        r = str(_groq_json(PROMPT_ZE.format(arroba=arroba, usuario=p["usuario"], instrucao=instrucao[:600],
                                            conversa=_texto_conversa(p, ig_id))).get("resposta", "")).strip()
        if not r or len(r) > 900:
            return "❌ A IA não conseguiu escrever agora. Mande de novo ou use: /ze nome texto pronto", None
        if not _seguro(r, t):
            return ("❌ A IA escreveu link, @, telefone ou pix que você não pediu; não usei. "
                    "Mande o texto pronto com: /ze " + p["usuario"] + " ..."), None
        ultima = next((x.get("message") for x in p["msgs"]
                       if str((x.get("from") or {}).get("id")) == p["autor"] and x.get("message")), "")
        partes = [f"✍️ Rascunho do Zé para @{p['usuario']} (direct do {arroba})"]
        if ultima:
            partes.append(f"Última mensagem dela(e): \"{ultima[:200]}\"")
        if (aviso := _janela(p["horas"])):
            partes.append(aviso)
        partes += ["", INICIO_RASCUNHO, r, FIM_RASCUNHO, "",
                   "Toque em ✅ Enviar para mandar. Para mudar: segure esta mensagem → Responder → escreva o texto "
                   "certo (vai do jeito que você escrever).", "", ref(perfil, p["autor"])]
        print(f"✍️  Rascunho para @{cofre.oculto(p['usuario'])} ({perfil})")
        return "\n".join(partes), BOTOES_RASCUNHO
    except Exception as e:
        print(f"⚠️  Comando do direct falhou: {e}")
        return (f"❌ Não consegui: {str(e)[:250]}\n(Se já passou de 24h da última mensagem da pessoa, "
                "o Instagram não deixa mais responder.)"), None


def rascunho(texto_previa):
    """Texto do rascunho dentro da prévia do Telegram (entre ▼▼▼ e ▲▲▲), ou ''."""
    m = re.search(re.escape(INICIO_RASCUNHO) + r"\n(.*?)\n" + re.escape(FIM_RASCUNHO), texto_previa or "", re.S)
    return m.group(1).strip() if m else ""
