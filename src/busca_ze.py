"""🔎 Busca do Zé — post fixo que funciona como ferramenta de busca.

O seguidor comenta o que procura no post fixado (legenda com #BuscaDoZe). Na mesma rodada do
responder (o webhook acorda o robô na hora), o Zé busca na Shopee, escolhe até 3 achados bons
e manda no direct da pessoa (resposta privada ao comentário, com um botão por achado).
No comentário, responde em público: "Te mandei no direct!".

Vale para todo post com #BuscaDoZe na legenda: a foto fixada e os Reels do rodízio (src/busca_reels.py). A limpeza de
15 dias não o apaga, porque ela só mexe nos posts que o robô registrou.

Vale também em TODOS os Reels de oferta (últimos 7 dias): ali, o comentário que pede OUTRO produto
("procuro uma air fryer", "tem cabeceira com pés?") vira busca. "Quero", "preço", "link" ou pedido
do próprio produto do Reels continuam com o responder (link da oferta no direct).
"""
import json
from datetime import timedelta

from . import config, vendas

ANA = config.PERFIL == "ana"   # 💚 Busca da Ana: mesma ferramenta, com o jeito dela e #BuscaDaAna
ARQ = config.PASTA_PERFIL / "busca_ze.json"
TAG = "buscadaana" if ANA else "buscadoze"
AVISO_ANA = "(são links de afiliada: você paga o mesmo e me ajuda a continuar caçando achadinhos 💚)"
MAX_POR_RODADA = 15
ACHADOS = 3

PUBLICAS = ["@{u} o Zé achou! ⛏️ Te mandei no direct 📩",
            "Achei, @{u}! 🤠 Confere o seu direct 📲",
            "@{u} garimpado! ⛏️ Os achados estão no seu direct 💌"]
PUBLICA_NADA = ("@{u} o Zé cavou, cavou e não achou nada bom de \"{t}\" ainda 😅 "
                "Tenta com outras palavras (ex.: \"fone bluetooth\")!")
if ANA:
    PUBLICAS = ["@{u} achei! 💚 Te mandei no direct", "Prontinho, @{u}! Olha o seu direct 🥰",
                "@{u} separei uns achadinhos pra você, tá no direct ✨"]
    PUBLICA_NADA = ("@{u} procurei \"{t}\" mas não achei nada bom o bastante ainda 😕 "
                    "Me fala com outras palavras (ex.: \"bolsa transversal\") que eu tento de novo! 💚")


def _agora():
    from .garimpar import agora
    return agora()


def _fmt():
    from .garimpar import FMT
    return FMT


def carregar():
    if ARQ.exists():
        return json.loads(ARQ.read_text(encoding="utf-8"))
    return {"ids": [], "procurado_em": "", "comentarios": {}}


def salvar(d):
    limite = (_agora() - timedelta(days=60)).strftime(_fmt())
    d["comentarios"] = {k: v for k, v in d["comentarios"].items() if v.get("em", "") >= limite}
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def posts_da_busca(api, ig_id, d):
    """Todos os posts com #BuscaDoZe (foto fixada + Reels do rodízio).
    Uma vez achado, o post fica na lista para sempre (o fixado some da listagem da API com o tempo);
    a cada hora o robô olha os posts novos atrás de outro #BuscaDoZe."""
    ids = d.setdefault("ids", [])
    if d.get("id_post") and d["id_post"] not in ids:   # formato antigo (um post só)
        ids.append(d.pop("id_post"))
    d.pop("id_post", None)
    espera = timedelta(hours=1) if ids else timedelta(0)   # sem nenhum post ainda: procura toda rodada
    if not d.get("procurado_em") or d["procurado_em"] <= (_agora() - espera).strftime(_fmt()):
        d["procurado_em"] = _agora().strftime(_fmt())
        try:
            corpo = api._req("GET", f"{ig_id}/media", params={"fields": "id,caption", "limit": 50})
            for m in corpo.get("data", []):
                if TAG in (m.get("caption") or "").lower().replace(" ", "") and m["id"] not in ids:
                    ids.append(m["id"])
                    print(f"🔎 Novo post da Busca do Zé: {m['id']}")
        except Exception as e:
            print(f"⚠️  Busca do Zé: não consegui listar os posts ({e})")
    # Reels do rodízio: entram direto pelo registro de quando o robô publicou (não dependem da listagem)
    arq_reels = config.PASTA_PERFIL / "busca_reels.json"
    if arq_reels.exists():
        try:
            for p in json.loads(arq_reels.read_text(encoding="utf-8")).get("posts", []):
                pid = p.get("id_post")
                if pid and p.get("status") == "postado" and pid not in ids and pid not in d.get("removidos", []):
                    ids.append(pid)
                    print(f"🔎 Reels da Busca do Zé incluído: {pid}")
                elif pid and p.get("status") == "apagado" and pid in ids:
                    ids.remove(pid)
        except Exception as e:
            print(f"⚠️  Busca do Zé: não li o registro dos Reels ({e})")
    return list(ids)


def termo(texto):
    """No post fixo todo comentário é uma busca: a IA limpa o texto; sem IA, tira as palavras vazias."""
    from . import pedidos
    if config.GROQ_API_KEY:
        t = pedidos._refinar({"texto": texto, "termo": ""})
        if t is not None:
            return t
    return pedidos.termo_do_comentario(texto, exigir_pedido=False)


PRECO_MAX = float(__import__("os").getenv("BUSCA_PRECO_MAX", "0"))   # 0 = sem limite de preço na Busca do Zé
ACESSORIOS = set("""capa capinha case pelicula peliculas protetor protecao carregador carregadores cabo cabos
suporte suportes tomada adaptador adaptadores refil refis pecas peca reposicao kit kits bolsa bolsinha estojo
porta organizador adesivo adesivos skin skins alca cordao chaveiro tampa tampas filtro filtros escova escovas
lente lentes bateria baterias fonte controle capas lencol lencois fronha fronhas colcha colchas edredom
cobertor manta saia""".split())
# palavras que não contam como "começo do nome" (o produto pedido tem que vir logo no início do título)
VAZIAS = set("""de do da dos das para pra com sem e o a os as em no na kit novo nova original oferta promocao
jogo conjunto super top premium lancamento envio imediato pronta entrega frete gratis""".split())
POSICAO_MAX = 4   # o núcleo do pedido tem que estar entre as 4 primeiras palavras que contam do nome
PREPOSICOES = r"(?:para|pra|p/|de|do|da|no|na|em|com)"


def _norm(txt):
    import unicodedata
    return unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode().lower()


def _raiz(p):
    """Singular aproximado: 'celulares' → 'celular', 'panelas' → 'panela'."""
    for suf, troca in (("oes", "ao"), ("aes", "ao"), ("res", "r"), ("zes", "z"), ("is", "l"), ("s", "")):
        if len(p) > 4 and p.endswith(suf):
            return p[: -len(suf)] + troca
    return p


def _palavras(txt):
    import re
    return [_raiz(p) for p in re.findall(r"[a-z0-9]+", _norm(txt))]


def relevante(nome, t):
    """O produto É o que a pessoa pediu? Todas as palavras do pedido no nome, e não pode ser
    acessório "de/para" a coisa pedida (capinha de celular, suporte para celular...)."""
    import re
    pedido = [p for p in _palavras(t) if len(p) > 2 and p not in ("para", "pra", "com", "sem")]
    nome_p = _palavras(nome)
    if not pedido or not all(any(n.startswith(p) for n in nome_p) for p in pedido):
        return False
    # "cama casal" ≠ "Lençol Queen 400 Fios ... Cama Casal": o que a pessoa pediu tem que ser
    # o próprio produto, ou seja, aparecer no começo do título, não só citado no meio/fim.
    cabeca = [n for n in nome_p if not n.isdigit() and n not in VAZIAS][:POSICAO_MAX]
    if not any(n.startswith(pedido[0]) for n in cabeca):
        return False
    if cabeca[0].startswith(pedido[0]):        # nome já começa pelo que foi pedido ("Kit 2 Travesseiros")
        return True
    if not (set(pedido) & ACESSORIOS):          # pediu o produto, não um acessório
        if set(nome_p[:4]) & ACESSORIOS:         # nome começa com o acessório ("Capa ... celular")
            return False
        nucleo = re.escape(_palavras(t)[0])
        if re.search(rf"\b{PREPOSICOES}\s+(?:o\s+|a\s+|seu\s+|sua\s+)?{nucleo}", _norm(nome)):
            return False                          # "... para celular", "... de celular"
    return True


def _aceitavel(o, rigoroso=True):
    nome = o["nome"].lower()
    if not (o["link_afiliado"] and o["imagem"] and 0 < o["preco"] and (not PRECO_MAX or o["preco"] <= PRECO_MAX)
            and not any(p in nome for p in config.PALAVRAS_PROIBIDAS)):
        return False
    if rigoroso:
        return o["nota"] >= 4.5 and o["vendas"] >= 50
    return o["nota"] >= 4.3 and o["vendas"] >= 10


PROMPT_IA = """Um cliente pediu na Shopee: "{t}".
Abaixo, produtos encontrados (número: nome). Quais SÃO o próprio produto que ele pediu?
Não conta acessório, peça, capa, suporte, refil, nem produto de outro tipo que só cita a palavra
(ex.: pediu "cama casal" → lençol, colcha ou protetor "para cama casal" NÃO servem; só a cama).
Responda só com JSON {{"ok": [números]}}, do mais adequado para o menos.

{lista}"""


def _filtro_ia(t, ofs):
    """A IA confere se cada produto é mesmo o pedido. None se a IA não respondeu."""
    if not config.GROQ_API_KEY or not ofs:
        return None
    import re
    from .legenda import _chamar_groq
    lista = "\n".join(f"{i}: {o['nome'][:110]}" for i, o in enumerate(ofs))
    try:
        bruto = _chamar_groq(PROMPT_IA.format(t=t.replace('"', "'"), lista=lista))
        nums = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("ok", [])
        return [ofs[int(n)] for n in nums if str(n).isdigit() and int(n) < len(ofs)]
    except Exception as e:
        print(f"⚠️  IA não conferiu a busca ({e}); fico só com as regras.")
        return None


def _pontos(o):
    return (o["nota"] >= 4.8, min(o["vendas"], 5000) * o["nota"] + o["comissao"] * 30)


def _mesmo_produto(a, b):
    """Dois anúncios do mesmo produto (outra loja, outra cor, título quase igual)?"""
    from difflib import SequenceMatcher
    pa = {w for w in _palavras(a["nome"]) if len(w) > 2}
    pb = {w for w in _palavras(b["nome"]) if len(w) > 2}
    if pa and pb and len(pa & pb) / len(pa | pb) >= 0.6:
        return True
    return SequenceMatcher(None, _norm(a["nome"])[:80], _norm(b["nome"])[:80]).ratio() >= 0.8


def _sem_repetidos(ofs):
    """Mantém a ordem, mas junta anúncios do mesmo produto e fica com o mais barato."""
    escolhidos = []
    for o in ofs:
        for i, e in enumerate(escolhidos):
            if _mesmo_produto(o, e):
                if o["preco"] < e["preco"]:
                    escolhidos[i] = o
                break
        else:
            escolhidos.append(o)
    return escolhidos


def achados(t):
    """Até 3 produtos que SÃO o que a pessoa pediu: busca por relevância (e mais vendidos),
    regras contra acessórios, e a IA confere a lista final."""
    from . import shopee
    from .garimpar import normalizar
    nos = []
    for pagina, ordem in ((1, 1), (2, 1), (1, 2)):
        try:
            nos += shopee.buscar_ofertas(t, pagina, 50, ordem)
        except Exception as e:
            print(f"⚠️  Shopee (página {pagina}, ordem {ordem}): {e}")
    vistos, unicos = set(), []
    for n in nos:
        o = normalizar(n, "busca", t)
        if o["id"] not in vistos:
            vistos.add(o["id"])
            unicos.append(o)
    certos = [o for o in unicos if relevante(o["nome"], t)]
    for rigoroso in (True, False):
        bons = sorted((o for o in certos if _aceitavel(o, rigoroso)), key=_pontos, reverse=True)[:15]
        if not bons:
            continue
        conferidos = _filtro_ia(t, bons)
        if conferidos is not None:
            bons = conferidos
        bons = _sem_repetidos(bons)
        if bons:
            return bons[:ACHADOS]
    return []


def _curto(nome, n=45):
    nome = " ".join(nome.split())
    return nome if len(nome) <= n else nome[:n - 1].rstrip() + "…"


def mensagem(t, ofs):
    linhas = [(f"Oi! 💚 Aqui é a Ana. Procurei \"{t}\" na Shopee e separei pra você:" if ANA
               else f"Oi! 🤠 Aqui é o Zé Garimpo. Garimpei \"{t}\" na Shopee e separei:"), ""]
    for i, o in enumerate(ofs, 1):
        vendas = f"{o['vendas']:,}".replace(",", ".")
        nota = f"{o['nota']:.1f}".replace(".", ",")
        intl = " 🌎 internacional" if o.get("internacional") else ""
        linhas.append(f"{i}️⃣ {_curto(o['nome'])} — R$ {o['preco_fmt']} (⭐ {nota}, {vendas}+ vendidos){intl}")
    linhas += ["", "Toque no botão do que gostou 👇",
               (AVISO_ANA if ANA else f"(links de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")]
    return "\n".join(linhas)


def enviar_dm(api, ig_id, cid, t, ofs, destinatario=None):
    """Manda os achados no direct: como resposta privada a um comentário (cid) ou,
    numa conversa que a pessoa abriu, direto para ela (destinatario = id da pessoa)."""
    para = {"id": destinatario} if destinatario else {"comment_id": cid}
    texto = mensagem(t, ofs)
    botoes = [{"type": "web_url", "url": vendas.do_canal(o, "zebusca"), "title": f"🛒 Ver achado {i}"}
              for i, o in enumerate(ofs, 1)]
    try:
        return api._req("POST", f"{ig_id}/messages", json={
            "recipient": para,
            "message": {"attachment": {"type": "template", "payload": {
                "template_type": "button", "text": texto[:640], "buttons": botoes}}}})
    except Exception as e:   # plano B: texto com os links
        print(f"⚠️  Botões recusados ({e}); mandando os links no texto.")
        links = "\n".join(f"{i}️⃣ {vendas.do_canal(o, 'zebusca')}" for i, o in enumerate(ofs, 1))
        return api._req("POST", f"{ig_id}/messages", json={"recipient": para, "message": {
            "text": f"{texto.split('Toque no botão')[0].strip()}\n\n{links}\n\n"
                    + (AVISO_ANA if ANA else f"(links de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")}})


# ------------------------------------------------------------------ busca pelo direct
JANELA_DM = timedelta(hours=23)       # o Instagram só deixa responder até 24h depois da mensagem
SILENCIO_HUMANO = timedelta(hours=2)  # se o Fred escreveu na conversa há pouco, o robô não se mete
MARCAS_ROBO = ("Oi! 😊", "Oi! 🤠", "Oi! 💚", "Oiê!", "Oi, amiga!", "Aaah", "Prontinho!", "Oi! Esse")   # começo das mensagens automáticas (não contam como o Fred)
DM_NADA = ("Oi! 🤠 Aqui é o Zé Garimpo. Cavei \"{t}\" na Shopee, mas não achei nada bom o bastante 😅 "
           "Me manda com outras palavras (ex.: \"fone bluetooth\", \"air fryer 5 litros\") que eu tento de novo!")
if ANA:
    DM_NADA = ("Oi! 💚 Aqui é a Ana. Procurei \"{t}\" na Shopee, mas não achei nada bom o bastante 😕 "
               "Me manda com outras palavras (ex.: \"bolsa transversal\", \"escova secadora\") que eu tento de novo!")
# "quero" solto no direct (sem dizer qual achado): pergunta qual; a resposta vira busca ("Bora garimpar")
DM_QUAL = ("Oi! 🤠 Aqui é o Zé Garimpo. Bora garimpar! ⛏️\n\nQual achado você quer? Me manda o nome do produto "
           "(ex.: \"câmera wi-fi\", \"kit lavabo\") que eu te mando o link aqui.\n\n"
           "Dica: comentando QUERO no post, o link chega sozinho no direct 😉")
if ANA:
    DM_QUAL = ("Oi, amiga! 💚 Bora garimpar? Qual achado você quer? Me manda o nome do produto "
               "(ex.: \"bolsa transversal\", \"escova secadora\") que eu te mando o link aqui.\n\n"
               "Dica: comentando QUERO no post, o link chega sozinho no direct 😉")


def _avisar_fred(reg):
    """Mensagem do direct que o robô não respondeu → alerta no Telegram privado do Fred."""
    import os
    from . import telegram
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if not (chat and os.getenv("TELEGRAM_BOT_TOKEN", "").strip()):
        return
    from datetime import datetime
    ate = (datetime.strptime(reg["em"], _fmt()) + timedelta(hours=24)).strftime("%d/%m %H:%M")
    quem = f"@{reg['usuario']}" if reg.get("usuario") else "alguém"
    texto = (f"📩 Direct do {config.ARROBA} sem resposta do robô\n\n"
             f"{quem}: \"{(reg.get('texto') or '')[:300]}\"\n\nResponda você até {ate} (depois o Instagram fecha a conversa).")
    try:
        telegram._api("sendMessage", data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"})
    except Exception as e:
        print(f"⚠️  Alerta do direct no Telegram falhou: {e}")


def _quando(txt):
    """'2026-10-10T12:09:48+0000' → data e hora de Brasília."""
    from datetime import datetime, timezone
    from .garimpar import BRT
    try:
        return datetime.strptime(txt[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(BRT)
    except (TypeError, ValueError):
        return None


def _conversas(api, ig_id):
    """Conversas do direct com as últimas mensagens (mais recentes primeiro)."""
    base = "id,updated_time,messages.limit(6){id,message,from,created_time%s}"
    try:   # com os anexos (prints para o "Zé, isso vale a pena?")
        corpo = api._req("GET", f"{ig_id}/conversations", params={
            "platform": "instagram", "limit": 25, "fields": base % ",attachments{image_data{url}}"})
    except Exception as e:
        print(f"⚠️  Direct: a API não aceitou ler os anexos ({str(e)[:150]}); lendo só o texto.")
        corpo = api._req("GET", f"{ig_id}/conversations", params={
            "platform": "instagram", "limit": 25, "fields": base % ""})
    return corpo.get("data", [])


def _imagem(msg):
    """URL da primeira imagem anexada à mensagem (print), se houver."""
    for a in (msg.get("attachments") or {}).get("data") or []:
        url = (a.get("image_data") or {}).get("url")
        if url:
            return url
    return None


# ------------------------------------------------------------------ perguntas prontas do direct (ice breakers)
TELEGRAM = "https://t.me/garimpovipofertas"
ATALHOS = [   # (pergunta que aparece no direct, código) — máximo 4
    ("🔎 Zé, procura um produto pra mim!", "BUSCA_ZE"),
    ("🔥 Quais as ofertas de hoje?", "OFERTAS_HOJE"),
    ("🎟️ Tem cupom hoje?", "CUPONS"),
    ("💬 Quero falar com o Garimpo VIP", "HUMANO"),
]
SILENCIO_PEDIDO = timedelta(hours=24)   # depois do "quero falar com o Garimpo VIP", o robô fica quieto


def _sem_emoji(txt):
    import re
    return re.sub(r"[^a-z0-9 ]", "", _norm(txt)).strip()


def atalho_do_texto(texto):
    alvo = _sem_emoji(texto)
    return next((cod for perg, cod in ATALHOS if _sem_emoji(perg) == alvo), None)


def configurar_atalhos(api):
    """Grava as perguntas prontas no direct da página (aparecem para quem abre a conversa pela 1ª vez)."""
    corpo = {"platform": "instagram", "ice_breakers": [
        {"locale": "default", "call_to_actions": [{"question": q, "payload": c} for q, c in ATALHOS]}]}
    ig_id = api.conferir_conta()["user_id"]
    r = api._req("POST", f"{ig_id}/messenger_profile", json=corpo)
    print(f"::notice::Perguntas do direct configuradas: {r}")
    print(api._req("GET", f"{ig_id}/messenger_profile", params={"fields": "ice_breakers"}))


def _ofertas_recentes(n=3):
    from .garimpar import carregar_fila
    ofs = [o for o in carregar_fila()["ofertas"].values()
           if o.get("status") == "postado" and o.get("link_afiliado") and o.get("postado_em")]
    return sorted(ofs, key=lambda o: o["postado_em"], reverse=True)[:n]


def responder_atalho(api, ig_id, autor, cod, d):
    """Resposta de cada pergunta pronta. Devolve a resposta da API (ou None)."""
    enviar = lambda msg: api._req("POST", f"{ig_id}/messages", json={"recipient": {"id": autor}, "message": msg})
    if cod == "BUSCA_ZE":
        return enviar({"text": "Oi! 🤠 Aqui é o Zé Garimpo. Bora garimpar! ⛏️\n\nMe diz o que você procura "
                               "(ex.: \"fone bluetooth\", \"air fryer\", \"tênis de corrida\") que eu te mando "
                               "os 3 melhores achados da Shopee, com nota alta e muita venda."
                               + ("\n\n🤔 Viu um produto e ficou na dúvida? Me manda o link (ou um print) "
                                  "que eu te digo se vale a pena!" if config.VALE_A_PENA_ATIVO else "")})
    if cod == "OFERTAS_HOJE":
        ofs = _ofertas_recentes()
        if not ofs:
            return enviar({"text": f"Oi! 🤠 Aqui é o Zé Garimpo. As ofertas do dia saem no feed e no Telegram: {TELEGRAM} 💎"})
        linhas = ["Oi! 🤠 Aqui é o Zé Garimpo. Os últimos achados da página:", ""]
        for i, o in enumerate(ofs, 1):
            linhas.append(f"{i}️⃣ {_curto(o.get('titulo') or o.get('nome', ''))} — R$ {o['preco_fmt']}")
        linhas += ["", f"Tem muito mais no Telegram: {TELEGRAM}",
                   (AVISO_ANA if ANA else f"(links de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")]
        botoes = [{"type": "web_url", "url": vendas.do_canal(o, "zebusca"), "title": f"🛒 Ver achado {i}"}
                  for i, o in enumerate(ofs, 1)]
        return enviar({"attachment": {"type": "template", "payload": {
            "template_type": "button", "text": "\n".join(linhas)[:640], "buttons": botoes}}})
    if cod == "CUPONS":
        return enviar({"text": "Oi! 🤠 Aqui é o Zé Garimpo. Os cupons e campanhas da Shopee saem primeiro no "
                               f"nosso canal do Telegram, assim que a Shopee libera 🎟️\n\n👉 {TELEGRAM}\n\n"
                               "E se procura algo específico, é só me dizer o nome do produto que eu garimpo!"})
    if cod == "HUMANO":
        d.setdefault("humano", {})[autor] = _agora().strftime(_fmt())
        return enviar({"text": "Oi! 😊 Pode mandar sua mensagem que a gente responde por aqui assim que possível 💛"})
    return None


def rodar_dms(api, minha):
    """Quem manda no direct o que procura ("procuro uma air fryer") recebe os 3 achados na hora."""
    if config.PERFIL not in ("garimpo", "ana"):
        return 0
    d = carregar()
    ig_id = minha["user_id"]
    feitos_ids = d.setdefault("dms", {})
    from . import story_dm
    de_story = story_dm.tratados()   # "quero" em resposta a story: o link já foi pelo story_dm
    enviados_robo = set(d.setdefault("msgs_robo", []))
    try:
        conversas = _conversas(api, ig_id)
    except Exception as e:
        print(f"⚠️  Busca do Zé no direct: não consegui ler as conversas ({e})")
        return 0
    agora = _agora()
    feitos = 0
    for conv in conversas:
        msgs = (conv.get("messages") or {}).get("data") or []
        if not msgs:
            continue
        ultima = msgs[0]                                    # a API manda da mais nova para a mais velha
        autor = (ultima.get("from") or {}).get("id")
        imagem = _imagem(ultima)
        if autor == ig_id or ultima["id"] in feitos_ids or ultima["id"] in de_story or not (ultima.get("message") or imagem):
            continue
        quando = _quando(ultima.get("created_time", ""))
        if not quando or agora - quando > JANELA_DM:
            continue
        humano = [m for m in msgs[1:] if (m.get("from") or {}).get("id") == ig_id and m["id"] not in enviados_robo
                  and m.get("message") and not m["message"].startswith(MARCAS_ROBO)]
        if humano and (q := _quando(humano[0].get("created_time", ""))) and agora - q < SILENCIO_HUMANO:
            continue                                        # o Fred está conversando: deixa com ele
        pediu_humano = d.get("humano", {}).get(autor)
        if pediu_humano and pediu_humano >= (agora - SILENCIO_PEDIDO).strftime(_fmt()):
            continue                                        # pediu para falar com gente: deixa com o Fred
        if feitos >= MAX_POR_RODADA:
            break
        from . import pedidos, vale_a_pena
        texto = ultima.get("message") or ""
        cod = atalho_do_texto(texto) if texto else None
        if cod:                                             # tocou numa pergunta pronta do direct
            try:
                r = responder_atalho(api, ig_id, autor, cod, d)
                if (r or {}).get("message_id"):
                    enviados_robo.add(r["message_id"])
                status = "atalho"
                print(f"📩 Direct: pergunta pronta {cod}.")
            except Exception as e:
                status = f"erro: {str(e)[:200]}"
                print(f"::warning::Pergunta pronta {cod}: {e}")
            feitos_ids[ultima["id"]] = {"autor": autor, "texto": texto, "atalho": cod, "status": status,
                                        "em": agora.strftime(_fmt())}
            feitos += 1
            continue
        if config.VALE_A_PENA_ATIVO and (vale_a_pena.tem_link(texto) or imagem):   # 🤔 "Zé, isso vale a pena?"
            reg = {"autor": autor, "texto": texto, "imagem": bool(imagem), "em": agora.strftime(_fmt())}
            try:
                r, status = vale_a_pena.responder(api, ig_id, autor, texto, imagem)
                if (r or {}).get("message_id"):
                    enviados_robo.add(r["message_id"])
                reg["status"] = f"vale_a_pena: {status}"
                print(f"📩 Direct: vale a pena? → {status}.")
            except Exception as e:
                reg["status"] = f"erro: {str(e)[:200]}"
                print(f"::warning::Vale a pena no direct: {e}")
            feitos_ids[ultima["id"]] = reg
            if reg["status"] != "vale_a_pena: ignorado":
                feitos += 1
            continue
        anterior = msgs[1] if len(msgs) > 1 else {}
        acabou_de_perguntar = ((anterior.get("from") or {}).get("id") == ig_id
                               and "Bora garimpar" in (anterior.get("message") or ""))
        # logo depois do "me diz o que você procura", qualquer resposta é a busca ("air fryer")
        # no direct, só o nome do produto já é busca ("fogão"); a IA barra "oi", "obrigado"...
        t = termo(texto) if (acabou_de_perguntar or config.GROQ_API_KEY) else pedidos._termo(texto)
        reg = {"autor": autor, "usuario": (ultima.get("from") or {}).get("username", ""), "texto": texto,
               "termo": t, "em": agora.strftime(_fmt())}
        if not t:
            from .responder import pediu_link
            if pediu_link(texto) and not acabou_de_perguntar:   # "quero" solto: pergunta qual achado
                try:
                    r = api._req("POST", f"{ig_id}/messages", json={"recipient": {"id": autor},
                                                                    "message": {"text": DM_QUAL}})
                    if (r or {}).get("message_id"):
                        enviados_robo.add(r["message_id"])
                    reg["status"] = "perguntou_qual"
                    feitos += 1
                    print("📩 Direct: \"quero\" solto → perguntei qual achado.")
                except Exception as e:
                    reg["status"] = f"erro: {str(e)[:200]}"
                    print(f"::warning::Direct: não consegui perguntar qual achado: {e}")
                    _avisar_fred(reg)
            else:
                reg["status"] = "ignorado"
                _avisar_fred(reg)
            feitos_ids[ultima["id"]] = reg
            continue
        try:
            ofs = achados(t)
        except Exception as e:
            print(f"⚠️  Busca do Zé no direct '{t}' falhou: {e}")
            continue
        try:
            if ofs:
                r = enviar_dm(api, ig_id, None, t, ofs, destinatario=autor)
                reg.update({"status": "entregue", "achados": [o["id"] for o in ofs]})
            else:
                r = api._req("POST", f"{ig_id}/messages", json={"recipient": {"id": autor},
                                                                "message": {"text": DM_NADA.format(t=t)}})
                reg["status"] = "nao_achou"
            if (r or {}).get("message_id"):
                enviados_robo.add(r["message_id"])
            feitos += 1
            print(f"📩 Direct: '{t}' → {len(ofs)} achados.")
        except Exception as e:
            reg["status"] = f"erro: {str(e)[:200]}"
            print(f"::warning::Busca do Zé no direct: não consegui responder: {e}")
            _avisar_fred(reg)
        feitos_ids[ultima["id"]] = reg
    limite = (agora - timedelta(days=30)).strftime(_fmt())
    d["dms"] = {k: v for k, v in feitos_ids.items() if v.get("em", "") >= limite}
    d["msgs_robo"] = list(enviados_robo)[-300:]
    salvar(d)
    return feitos


def _mesmo_pedido(t, titulo):
    """O pedido é do próprio produto do Reels? ('onde compra esse fone' no Reels de um fone → sim)."""
    nome = _palavras(titulo)
    pedido = [p for p in _palavras(t) if len(p) > 2 and p not in VAZIAS]
    return bool(pedido) and any(n.startswith(p) or p.startswith(n) for p in pedido for n in nome if len(n) > 2)


def tomados():
    """Comentários de Reels de oferta que a Busca do Zé já atendeu (o responder não manda o link deles)."""
    return {k for k, v in carregar().get("comentarios", {}).items()
            if v.get("reels_oferta") and v.get("status") not in ("link", "ignorado")}


def rodar(api, minha, ja_respondidos=None):
    """Atende os comentários novos do post fixo. Devolve quantas buscas entregou."""
    if config.PERFIL not in ("garimpo", "ana"):
        return 0
    d = carregar()
    ig_id = minha["user_id"]
    coms = []
    from .responder import numero_pedido, pediu_link, posts_top, so_pediu_link
    tops = posts_top()   # carrosséis do Top 5: comentário com pedido de produto vira busca;
    for post in tops:    # "QUERO 3"/"QUERO" fica com o responder (link do produto do carrossel)
        try:
            coms += [dict(c, _top=len(tops[post].get("itens") or [])) for c in api.comentarios(post)]
        except Exception as e:
            print(f"⚠️  Busca do Zé: comentários do Top {post}: {e}")
    for post in posts_da_busca(api, ig_id, d):
        falhas = d.setdefault("falhas", {})
        try:
            coms += api.comentarios(post)
            falhas.pop(post, None)
        except Exception as e:   # post apagado (ex.: Reels antigo do rodízio): sai da lista após 3 erros seguidos
            falhas[post] = falhas.get(post, 0) + 1
            print(f"::warning::Busca do Zé: post {post} indisponível ({str(e)[:300]}) — tentativa {falhas[post]}/3.")
            if falhas[post] >= 3:
                d["ids"].remove(post)
                falhas.pop(post)
                d.setdefault("removidos", []).append(post)   # não volta pelo registro dos Reels
    # Reels de oferta: a Busca do Zé vale em todos
    try:
        from .garimpar import carregar_fila
        from .responder import posts_ativos
        for o in posts_ativos(carregar_fila()):
            if o.get("formato") != "reels" or o["id_post"] in d["ids"]:
                continue
            try:
                coms += [dict(c, _oferta=o.get("titulo") or o.get("nome", "")) for c in api.comentarios(o["id_post"])]
            except Exception as e:
                print(f"⚠️  Busca do Zé: comentários do Reels {o['id_post']}: {e}")
    except Exception as e:
        print(f"⚠️  Busca do Zé: não consegui ler os Reels de oferta ({e})")
    feitos = 0
    for c in coms:
        cid, autor = c["id"], (c.get("from") or {}).get("id")
        if cid in d["comentarios"] or autor == ig_id or c.get("username") == minha.get("username"):
            continue
        if feitos >= MAX_POR_RODADA:
            break
        usuario = c.get("username") or (c.get("from") or {}).get("username", "")
        texto = c.get("text", "")
        if c.get("_top") and (numero_pedido(texto, c["_top"]) or so_pediu_link(texto)):
            continue   # pediu link de um produto do Top: quem responde é o responder
        reg = {"usuario": usuario, "autor": autor, "texto": texto, "em": _agora().strftime(_fmt())}
        if "_oferta" in c:   # Reels de oferta: só vira busca se pedir OUTRO produto
            if so_pediu_link(texto):
                continue   # "quero", "link", "preço?" → responder manda o link da oferta
            from .pedidos import _termo
            t = _termo(texto)   # aqui só conta pedido de produto de verdade (elogio/pergunta ficam de fora)
            reg.update({"termo": t, "reels_oferta": True})
            if not t or _mesmo_pedido(t, c["_oferta"]):
                reg["status"] = "link" if pediu_link(texto) else "ignorado"   # é sobre o próprio produto
                d["comentarios"][cid] = reg
                continue
        else:
            t = termo(texto)
        reg["termo"] = t
        if not t:
            reg["status"] = "ignorado"   # elogio, emoji, marcação de amigo...
            d["comentarios"][cid] = reg
            continue
        try:
            ofs = achados(t)
        except Exception as e:
            print(f"⚠️  Busca do Zé '{t}' falhou: {e}")
            continue   # não registra: tenta de novo na próxima rodada
        try:
            if ofs:
                enviar_dm(api, ig_id, cid, t, ofs)
                api.responder_comentario(cid, PUBLICAS[len(d["comentarios"]) % len(PUBLICAS)].format(u=usuario))
                reg.update({"status": "entregue", "achados": [o["id"] for o in ofs]})
                print(f"🔎 @{usuario} buscou '{t}' → {len(ofs)} achados no direct.")
            else:
                api.responder_comentario(cid, PUBLICA_NADA.format(u=usuario, t=t))
                reg["status"] = "nao_achou"
                print(f"🔎 @{usuario} buscou '{t}' → nada bom o bastante.")
            feitos += 1
        except Exception as e:
            reg["status"] = f"erro: {str(e)[:200]}"
            print(f"::warning::Busca do Zé: não consegui responder @{usuario}: {e}")
        d["comentarios"][cid] = reg
    salvar(d)
    return feitos


if __name__ == "__main__":   # teste: python -m src.busca_ze "celular" "fone bluetooth"
    import sys
    if sys.argv[1:2] == ["conversas"]:   # diagnóstico: o que o robô enxerga no direct
        from . import instagram
        ig = instagram.conferir_conta()["user_id"]
        for c in _conversas(instagram, ig)[:8]:
            ms = (c.get("messages") or {}).get("data") or []
            u = ms[0] if ms else {}
            quem = "PÁGINA" if (u.get("from") or {}).get("id") == ig else "pessoa"
            print(f"::notice::{c.get('updated_time')} | última de {quem}: {(u.get('message') or '[sem texto]')[:60]!r} "
                  f"({u.get('created_time')})")
        sys.exit(0)
    if sys.argv[1:2] == ["posts"]:   # diagnóstico: posts do perfil e quantos comentários a API lê de cada
        from . import instagram
        ig = instagram.conferir_conta()["user_id"]
        corpo = instagram._req("GET", f"{ig}/media", params={
            "fields": "id,media_type,media_product_type,timestamp,caption,comments_count,permalink", "limit": 15})
        for m in corpo.get("data", []):
            try:
                n = len(instagram.comentarios(m["id"]))
            except Exception as e:
                n = f"erro {str(e)[:80]}"
            print(f"::notice::{m['id']} {m.get('media_product_type')} {m.get('timestamp')} "
                  f"coments={m.get('comments_count')}/{n} {m.get('permalink')} | {(m.get('caption') or '')[:50]!r}")
        sys.exit(0)
    if sys.argv[1:2] == ["atalhos"]:   # python -m src.busca_ze atalhos → grava as perguntas do direct
        try:
            from . import instagram
            configurar_atalhos(instagram)
        except Exception as e:
            print(f"::error::{str(e)[:500]}")
            sys.exit(1)
        sys.exit(0)
    for t in sys.argv[1:] or ["celular"]:
        print(f"\n🔎 {t}")
        try:
            for o in achados(termo(t) or t):
                print(f"  • R$ {o['preco_fmt']:>9} ⭐{o['nota']} {o['vendas']:>6} vend. — {o['nome'][:90]}")
        except Exception as e:
            print(f"  ⚠️  {e}")
