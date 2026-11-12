"""📸 Busca do Zé por FOTO — o seguidor manda no direct a foto de um produto (tirada por ele, print, foto de
outra loja) e o Zé reconhece o que é e devolve os 3 achados parecidos, igual à Busca do Zé por texto
(Shopee, Mercado Livre, AliExpress e lojas oficiais da Awin; no máximo 2 por loja; mesmos filtros).

Pedido do Fred em 12/11/2026. Ligado no direct pelo src/busca_ze.rodar_dms (mensagem com imagem),
só no Garimpo, com BUSCA_FOTO_ATIVO=1 (variável do workflow 3).

Quem lê a foto: Gemini (GEMINI_API_KEY, mesmo esquema do radar de virais); se falhar, um modelo de visão da Groq.
A IA devolve um termo de busca GENÉRICO, sem marca (o Garimpo não indica réplica de marca famosa).
Foto sem produto (selfie, meme, paisagem): o Zé pede uma foto mais de perto ou o nome do produto.
Cópia de toda resposta vai para o Telegram privado do Fred.

Teste (não manda nada para ninguém): python -m src.foto_ze URL_DA_FOTO [OUTRA_URL ...]
"""
import base64
import json
import os
import re

import requests

from . import config

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}
ATIVO = os.getenv("BUSCA_FOTO_ATIVO", "0") == "1"

PROMPT = """Uma pessoa mandou esta foto no direct de uma página de achadinhos (Shopee, Mercado Livre, AliExpress)
porque quer comprar esse produto ou um parecido.{texto}
Descubra qual é o produto principal da foto (o que está em destaque; se for print de loja, o produto anunciado).
Responda só com JSON:
{{"tem_produto": true/false, "o_que_e": "o produto em até 7 palavras, em português, começando com um/uma (ex.: uma mochila de couro marrom)",
  "busca": "termo de busca para achar um parecido numa loja online: 2 a 4 palavras em português, o tipo do
            produto + a característica que mais importa (material, formato, tamanho ou uso; cor só se for
            o que define o produto)",
  "busca_curta": "só o tipo do produto, 1 a 3 palavras (ex.: processador de alimentos, ring light, mochila)",
  "infantil": true/false}}
Regras:
- NÃO coloque marca nem nome de personagem/time/franquia na busca (ex.: tênis da Nike → "tênis corrida masculino
  branco"; caneca do Stitch → "caneca personagem azul"). Use as palavras que um brasileiro digitaria na Shopee.
- "infantil" é true só se o produto for claramente de criança/bebê.
- Se a foto não mostra um produto que dá para comprar (selfie, pessoa, meme, paisagem, comida pronta, animal,
  print de conversa, imagem sem foco), responda {{"tem_produto": false, "o_que_e": "", "busca": "", "busca_curta": "", "infantil": false}}."""

DM_INTRO = ("Oi! 🤠 Aqui é o Zé Garimpo. Recebi sua foto! Pelo que eu vi, é {o}. "
            "Garimpei parecidos e separei os melhores 👇")
DM_NAO_RECONHECI = ("Oi! 🤠 Aqui é o Zé Garimpo. Recebi sua foto, mas não consegui reconhecer o produto 😅 "
                    "Me manda uma foto mais de pertinho dele, ou escreve o nome (ex.: \"air fryer\", "
                    "\"tênis de corrida\"), que eu garimpo parecidos pra você! ⛏️")
DM_NADA = ("Oi! 🤠 Aqui é o Zé Garimpo. Vi na sua foto {o}, garimpei parecidos na Shopee, no Mercado Livre e no "
           "AliExpress, mas não achei de vendedor confiável 😅 Eu só mando produto bem avaliado e com muitas "
           "vendas, pra você não cair em furada.\n\nSe quiser, me escreve com outras palavras o que procura "
           "(cor, tamanho, pra que vai usar) que eu tento de novo! ⛏️")


# ------------------------------------------------------------------ ler a foto
def _baixar(url):
    """Bytes da foto (reduzida para 1024px se o Pillow estiver instalado) e o tipo."""
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    dados, tipo = r.content, (r.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
    try:
        from io import BytesIO
        from PIL import Image
        im = Image.open(BytesIO(dados)).convert("RGBA").convert("RGB")
        im.thumbnail((1024, 1024))
        buf = BytesIO()
        im.save(buf, "JPEG", quality=85)
        dados, tipo = buf.getvalue(), "image/jpeg"
    except Exception:
        pass   # o workflow 3 só instala o requests: vai a foto original mesmo
    if not tipo.startswith("image/"):
        tipo = "image/jpeg"
    return dados, tipo


def _json(bruto):
    return json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))


def _gemini(prompt, dados, tipo):
    chave = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not chave:
        return None
    from .radar_virais import GEMINI_URL, _modelos_gemini, config_geracao
    try:
        modelos = [m for m in _modelos_gemini(chave) if "lite" not in m][:3] or ["gemini-2.5-flash"]
    except Exception:
        modelos = ["gemini-2.5-flash"]
    partes = [{"text": prompt}, {"inline_data": {"mime_type": tipo, "data": base64.b64encode(dados).decode()}}]
    for modelo in modelos:
        try:
            r = requests.post(f"{GEMINI_URL}/models/{modelo}:generateContent", params={"key": chave}, timeout=40,
                              json={"contents": [{"parts": partes}], "generationConfig": config_geracao(modelo, 0.2)})
            if r.status_code == 503:   # "high demand": costuma passar em segundos
                import time
                time.sleep(4)
                r = requests.post(f"{GEMINI_URL}/models/{modelo}:generateContent", params={"key": chave}, timeout=40,
                                  json={"contents": [{"parts": partes}],
                                        "generationConfig": config_geracao(modelo, 0.2)})
            if r.status_code != 200:
                print(f"⚠️  Foto/Gemini {modelo}: HTTP {r.status_code} {' '.join(r.text[:160].split())}")
                continue
            lido = _json(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            print(f"👁️  Foto lida pelo Gemini ({modelo}).")
            return lido
        except Exception as e:
            print(f"⚠️  Foto/Gemini {modelo}: {str(e)[:120]}")
    return None


def _groq(prompt, dados, tipo):
    if not config.GROQ_API_KEY:
        return None
    from .vale_a_pena import _modelos_visao
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"}
    try:   # a Groq recusa foto grande ("Request too large"): manda em 512px
        from io import BytesIO
        from PIL import Image
        im = Image.open(BytesIO(dados)).convert("RGB")
        im.thumbnail((512, 512))
        buf = BytesIO()
        im.save(buf, "JPEG", quality=80)
        dados, tipo = buf.getvalue(), "image/jpeg"
    except Exception:
        pass
    url = f"data:{tipo};base64," + base64.b64encode(dados).decode()
    for modelo in _modelos_visao(headers)[:4]:
        try:
            r = requests.post(f"{config.GROQ_URL}/chat/completions", headers=headers, timeout=60, json={
                "model": modelo, "temperature": 0.2, "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]}]})
            if r.status_code != 200:
                print(f"⚠️  Foto/Groq {modelo}: HTTP {r.status_code} {r.text[:120]}")
                continue
            lido = _json(r.json()["choices"][0]["message"]["content"])
            print(f"👁️  Foto lida pela Groq ({modelo}).")
            return lido
        except Exception as e:
            print(f"⚠️  Foto/Groq {modelo}: {str(e)[:120]}")
    return None


def _proibido(t):
    """Palavra proibida como palavra inteira ("arma" barra "arma de pressão", não "armário");
    as compridas valem como começo ("erotic" barra "erotico")."""
    from .busca_ze import _norm
    for p in config.PALAVRAS_PROIBIDAS:
        p = _norm(p).strip()
        if p and re.search(rf"\b{re.escape(p)}{'' if len(p) >= 6 else r'\b'}", t):
            return True
    return False


def ler(url, texto=""):
    """{"o_que_e", "busca"} do produto da foto, ou None se não tem produto / a IA não leu."""
    try:
        dados, tipo = _baixar(url)
    except Exception as e:
        print(f"⚠️  Não baixei a foto do direct ({e}).")
        return None
    dica = f'\nA pessoa também escreveu: "{texto[:200]}".' if texto.strip() else ""
    prompt = PROMPT.format(texto=dica.replace("{", "(").replace("}", ")"))
    lido = _gemini(prompt, dados, tipo) or _groq(prompt, dados, tipo)
    print(f"   leitura: {lido}")
    if not lido or not lido.get("tem_produto"):
        return None
    from .busca_ze import _infantil, _norm

    def limpa(txt, n):
        t = " ".join(_norm(str(txt or "")).strip(" .!?\"'").split()[:n])
        if len(t) < 3 or _proibido(t):
            return ""
        if lido.get("infantil") and not _infantil(t):
            t += " infantil"   # sem isso a Busca do Zé tira os produtos de criança
        return t
    busca = limpa(lido.get("busca"), 5)
    curta = limpa(lido.get("busca_curta"), 4)
    if not busca:
        return None
    o = str(lido.get("o_que_e") or busca).strip().rstrip(".")
    return {"o_que_e": o[:60], "busca": busca, "curta": curta if curta and curta != busca else ""}


def achados(lido):
    """Os 3 parecidos: busca pelo termo da foto; se vier menos de 2, completa com a busca só pelo tipo."""
    from . import busca_ze
    t = lido["busca"]
    ofs = busca_ze.achados(t)
    if len(ofs) < 2 and lido.get("curta"):
        print(f"   poucos achados com \"{t}\": tentando só \"{lido['curta']}\"")
        mais = busca_ze.achados(lido["curta"])
        if len(mais) > len(ofs):
            ids = {o["id"] for o in mais}
            ofs, t = mais + [o for o in ofs if o["id"] not in ids], lido["curta"]
    return ofs[:busca_ze.ACHADOS], t


# ------------------------------------------------------------------ responder no direct
def _copia_fred(usuario, autor, url, lido, ofs, status):
    """Cópia no Telegram privado do Fred: a foto, o que o Zé entendeu e o que mandou."""
    from . import direct_telegram
    from .busca_ze import _curto, _nome_loja
    chat, token = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip(), os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not (chat and token):
        return
    quem = f"@{usuario}" if usuario else "alguém"
    linhas = [f"📸 {quem} mandou uma FOTO no direct do {config.ARROBA}"]
    if lido:
        linhas.append(f"🤠 O Zé entendeu: {lido['o_que_e']} (buscou \"{lido['busca']}\")")
    if ofs:
        linhas += ["", "Mandou:"] + [f"{i}. {_curto(o['nome'], 60)} — R$ {o['preco_fmt']} ({_nome_loja(o)})"
                                     for i, o in enumerate(ofs, 1)]
    else:
        linhas.append({"nao_reconheceu": "Não reconheceu o produto e pediu outra foto ou o nome.",
                       "nao_achou": "Não achou parecido de vendedor confiável e avisou a pessoa."}.get(status, status))
    linhas += ["", "Se errou: segure esta mensagem → Responder → escreva a resposta certa. Eu mando no direct.",
               "", direct_telegram.ref(config.PERFIL, autor)]
    texto = "\n".join(linhas)
    try:   # com a foto, para o Fred ver se o Zé acertou; se o Telegram não abrir o link, vai só o texto
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", timeout=30,
                          data={"chat_id": chat, "photo": url, "caption": texto[:1000]})
        if r.json().get("ok"):
            return
    except Exception:
        pass
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                      data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"})
    except Exception as e:
        print(f"⚠️  Cópia da foto no Telegram falhou: {e}")


def responder(api, ig_id, autor, url, texto="", usuario=""):
    """Lê a foto e responde no direct. Devolve (ids das mensagens do robô, status, termo)."""
    from . import busca_ze
    enviar = lambda msg: api._req("POST", f"{ig_id}/messages", json={"recipient": {"id": autor}, "message": msg})
    ids = []
    lido = ler(url, texto)
    if not lido:
        r = enviar({"text": DM_NAO_RECONHECI})
        ids.append((r or {}).get("message_id"))
        _copia_fred(usuario, autor, url, None, [], "nao_reconheceu")
        return ids, "nao_reconheceu", ""
    ofs, t = achados(lido)
    if not ofs:
        r = enviar({"text": DM_NADA.format(o=lido["o_que_e"])})
        ids.append((r or {}).get("message_id"))
        _copia_fred(usuario, autor, url, lido, [], "nao_achou")
        return ids, "nao_achou", t
    r = enviar({"text": DM_INTRO.format(o=lido["o_que_e"])})
    ids.append((r or {}).get("message_id"))
    r = busca_ze.enviar_dm(api, ig_id, None, t, ofs, destinatario=autor)
    ids.append((r or {}).get("message_id"))
    try:   # o Zé confere se acertou; a resposta vira detalhe da mesma busca
        r = enviar({"text": busca_ze.DM_CONFERE})
        ids.append((r or {}).get("message_id"))
    except Exception as e:
        print(f"⚠️  Não mandei a pergunta de conferência: {e}")
    _copia_fred(usuario, autor, url, lido, ofs, "entregue")
    return ids, "entregue", t


if __name__ == "__main__":
    import sys
    from . import busca_ze
    for u in sys.argv[1:]:
        print(f"\n📸 {u}")
        lido = ler(u)
        if not lido:
            print("   → sem produto reconhecido: o Zé pediria outra foto ou o nome.")
            continue
        print(f"   → o Zé entendeu: {lido['o_que_e']} | busca: \"{lido['busca']}\"")
        ofs, _t = achados(lido)
        print("   " + DM_INTRO.format(o=lido["o_que_e"]))
        for i, o in enumerate(ofs, 1):
            print(f"   {i}. {o['nome'][:80]} — R$ {o['preco_fmt']} ({busca_ze._nome_loja(o)}) "
                  f"⭐{o.get('nota')} {o.get('vendas')} vendas")
            print(f"      foto: {o.get('imagem')}")
        if not ofs:
            print("   " + DM_NADA.format(o=lido["o_que_e"]))
