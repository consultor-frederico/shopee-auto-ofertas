"""Quadro "Você pediu, o Zé achou!" (só Garimpo VIP).

1) coletar()  — roda no responder: lê os comentários dos posts do Zé (últimos 7 dias). Quem escreve o
   que procura ("fone bluetooth", "procuro uma air fryer") vira um pedido em data/.../pedidos.json e
   ganha resposta pública: "Anotado! O Zé já foi garimpar ...".
2) atender()  — roda no garimpo: para cada pedido novo, busca na Shopee, escolhe o melhor produto
   (nota, vendas e comissão) e põe na fila com prioridade e legenda "VOCÊ PEDIU, O ZÉ ACHOU!",
   marcando @quem pediu.
3) entregar() — roda logo depois que a oferta sai: manda o link no direct de quem pediu
   (resposta privada ao comentário original, que o Instagram aceita até 7 dias).
"""
import json
import re
import unicodedata
from datetime import datetime, timedelta

from . import config

ARQ = config.PASTA_PERFIL / "pedidos.json"
DIAS_JANELA = 7
MAX_TENTATIVAS = 3
POR_GARIMPO = 2

PARADAS = set("""quero queria procuro procurando busco buscando acha achar ache garimpa garimpar garimpe
ze zezinho jose por favor pfv pf pls preciso precisando gostaria seria bom tem algum alguma um uma uns umas
de do da dos das pra para pro o a os as e eu me mim voce vc oi ola bom dia boa tarde noite que um ai
favor ajuda ajudar me consegue consegui sim nao barato barata boa bom legal""".split())

RESPOSTAS = ["Anotado, @{u}! O Zé já foi garimpar {t} pra você ⛏️ Fica de olho na página!",
             "Pedido aceito, @{u}! O Zé tá cavando {t} na Shopee 🤠 Logo sai aqui!",
             "Boa, @{u}! {T} entrou na lista do Zé ⛏️ Quando ele achar, te aviso no direct!"]


def _agora():
    from .garimpar import agora
    return agora()


def _fmt():
    from .garimpar import FMT
    return FMT


def carregar():
    if ARQ.exists():
        return json.loads(ARQ.read_text(encoding="utf-8"))
    return {}


def salvar(dados):
    limite = (_agora() - timedelta(days=30)).strftime(_fmt())
    dados = {k: v for k, v in dados.items() if v.get("em", "") >= limite}
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _sem_acento(txt):
    return unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower()


# Pedidos sensíveis (lingerie, íntimo, sex shop...): NUNCA entram no quadro público nem marcam a pessoa.
# A resposta pública é neutra e o achado vai só no direct de quem pediu. A lista pega o óbvio; a IA cobre o resto.
SENSIVEIS = ["lingerie", "lingeri", "calcinha", "cueca", "sutia", "corset", "espartilho", "sexy", "sexual", "sensual",
             "sexo", "erotic", "intim", "consolo", "vibrador", "lubrificante", "camisinha", "preservativo",
             "porno", "bdsm", "fantasia sexual", "anticoncep", "pilula"]
# Palavras da config.PALAVRAS_PROIBIDAS que, para pedido privado, deixam de barrar (o resto continua barrado)
PROIBIDAS_LIBERADAS_NO_PRIVADO = ["sex", "erótic", "lingerie"]
RESPOSTA_PRIVADA_NEUTRA = "Anotado! Te chamo no direct 📩"


def sensivel_por_palavra(*textos):
    t = _sem_acento(" ".join(textos))
    return any(_sem_acento(w) in t for w in SENSIVEIS)


PEDE = re.compile(r"\b(procur|quer|queria|busc|ach|garimp|precis|gostaria|tem\b|traz|encontr)")


def termo_do_comentario(texto, exigir_pedido=True):
    """'Zé, procuro uma air fryer barata!' → 'air fryer'. Vazio se não parece pedido de produto.
    Sem IA, só aceita quando há verbo de pedido (procuro, queria, acha...), para não confundir elogio."""
    if exigir_pedido and not PEDE.search(_sem_acento(texto or "")):
        return ""
    t = re.sub(r"@\w[\w.]*", " ", texto or "")
    palavras = re.findall(r"[A-Za-zÀ-ÿ0-9]+", t)
    uteis = [p for p in palavras if _sem_acento(p) not in PARADAS]
    if not uteis or len(uteis) > 6 or len(" ".join(uteis)) < 3:
        return ""
    if all(p.isdigit() for p in uteis):
        return ""
    return " ".join(uteis).lower()[:50]


# ------------------------------------------------------------------ 1) coletar (responder)
def _posts_do_ze():
    from .ze import _carregar
    from .garimpar import BRT
    limite = _agora() - timedelta(days=DIAS_JANELA)
    return [p for p in _carregar().get("posts", []) if p.get("id_post")
            and datetime.strptime(p["postado_em"], _fmt()).replace(tzinfo=BRT) >= limite]


def coletar(api, minha):
    if config.PERFIL != "garimpo":
        return 0
    from .responder import pediu_link
    posts = _posts_do_ze()
    if not posts:
        return 0
    dados, novos = carregar(), 0
    for p in posts:
        try:
            coms = api.comentarios(p["id_post"])
        except Exception as e:
            print(f"⚠️  Comentários do post do Zé {p['id_post']}: {e}")
            continue
        for c in coms:
            cid, autor = c["id"], (c.get("from") or {}).get("id")
            if cid in dados or autor == minha["user_id"] or c.get("username") == minha.get("username"):
                continue
            usuario = c.get("username") or (c.get("from") or {}).get("username", "")
            texto = c.get("text", "")
            termo, sensivel = _pedido(texto)
            reg = {"post": p["id_post"], "usuario": usuario, "autor": autor, "texto": c.get("text", ""),
                   "termo": termo, "em": _agora().strftime(_fmt()), "status": "novo" if termo else "ignorado"}
            if termo and sensivel:
                reg["privado"] = True   # só direct: sem marcação, sem termo no público, sem post no quadro
                try:
                    api.responder_comentario(cid, RESPOSTA_PRIVADA_NEUTRA)
                    reg["resposta"] = "ok"
                except Exception as e:
                    reg["resposta"] = f"erro: {str(e)[:200]}"
                novos += 1
                print(f"🔒 Pedido sensível de @{usuario}: entrega só no direct.")
            elif termo:
                try:
                    modelo = RESPOSTAS[len(dados) % len(RESPOSTAS)]
                    api.responder_comentario(cid, modelo.format(u=usuario, t=termo, T=termo.capitalize()))
                    reg["resposta"] = "ok"
                except Exception as e:
                    reg["resposta"] = f"erro: {str(e)[:200]}"
                novos += 1
                print(f"🙋 Pedido de @{usuario}: {termo}")
            dados[cid] = reg
    salvar(dados)
    return novos


def _termo(texto):
    """Com a IA (Groq) decide se é pedido de produto; sem ela, só aceita com verbo de pedido."""
    if config.GROQ_API_KEY:
        termo = _refinar({"texto": texto, "termo": ""})
        if termo is not None:
            return termo
    return termo_do_comentario(texto)


# ------------------------------------------------------------------ 2) atender (garimpo)
PROMPT_TERMO = """Um seguidor de uma página de achadinhos da Shopee comentou: "{texto}"
Se ele está pedindo um produto, responda só com JSON {{"produto": "<termo curto de busca na Shopee, 1 a 4 palavras>", "sensivel": false}}.
Se o produto pedido é íntimo ou sexual (lingerie, roupa íntima, sex shop, produto erótico ou sensual), use "sensivel": true.
Se não é pedido de produto (elogio, piada, pergunta, spam, algo proibido como droga ou arma), responda {{"produto": "", "sensivel": false}}."""


def _classificar(texto):
    """(termo, sensível) segundo a IA. None se a IA não respondeu."""
    if not config.GROQ_API_KEY:
        return None
    from .legenda import _chamar_groq
    try:
        bruto = _chamar_groq(PROMPT_TERMO.format(texto=(texto or "")[:200].replace('"', "'")))
        dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
        termo = str(dados.get("produto", "")).strip().lower()[:50]
        return termo, bool(dados.get("sensivel")) and bool(termo)
    except Exception:
        return None


def _refinar(reg):
    """Termo de busca segundo a IA ("" = não é pedido ou é sensível). None se a IA não respondeu."""
    r = _classificar(reg["texto"])
    if r is None:
        return None
    termo, sensivel = r
    return "" if sensivel else termo


def _pedido(texto):
    """(termo, sensível) de um comentário. Termo vazio = não é pedido de produto."""
    from .responder import pediu_link
    if pediu_link(texto) and len(texto.split()) <= 3:
        return "", False
    r = _classificar(texto)
    if r is None:
        termo, ia_sensivel = termo_do_comentario(texto), False
    else:
        termo, ia_sensivel = r
    return termo, bool(termo) and (ia_sensivel or sensivel_por_palavra(termo, texto))


def _aceitavel(o, privado=False):
    nome = o["nome"].lower()
    proibidas = [p for p in config.PALAVRAS_PROIBIDAS if not (privado and p in PROIBIDAS_LIBERADAS_NO_PRIVADO)]
    return (o["link_afiliado"] and o["imagem"] and o["nota"] >= 4.5 and o["vendas"] >= 50
            and o["comissao"] >= 1 and 0 < o["preco"] <= config.PRECO_MAXIMO
            and not any(p in nome for p in proibidas))


def _melhor(nos, termo, fila, privado=False):
    from .garimpar import ja_usado, normalizar
    ofs = [normalizar(n, "pedido", termo) for n in nos]
    ofs = [o for o in ofs if _aceitavel(o, privado) and not ja_usado(fila, o["id"])]
    if not ofs:
        return None
    return max(ofs, key=lambda o: (o["nota"] >= 4.8, min(o["vendas"], 5000) * o["nota"] + o["comissao"] * 50))


def cabecalho(o):
    p = o["pedido"]
    return (f"🙋 VOCÊ PEDIU, O ZÉ ACHOU! ⛏️\n"
            f"@{p['usuario']} pediu \"{p['termo']}\" e o Zé foi garimpar pra você.")


CONVITE = "💬 Quer que o Zé garimpe algo pra você? Comenta o que procura no próximo post do Zé!"


def atender(fila):
    """Busca os pedidos novos e põe o achado na fila. Devolve quantos entraram."""
    if config.PERFIL != "garimpo":
        return 0
    from . import legenda, shopee
    dados = carregar()
    pendentes = [(k, v) for k, v in dados.items() if v.get("status") == "novo"]
    entrou = 0
    for cid, reg in pendentes[:POR_GARIMPO]:
        reg["tentativas"] = reg.get("tentativas", 0) + 1
        if reg.get("privado"):
            termo = reg["termo"]
            try:
                o = _melhor(shopee.buscar_ofertas(termo, 1, 40, 2), termo, fila, privado=True)
            except Exception as e:
                print(f"⚠️  Busca do pedido sensível '{termo}' falhou: {e}")
                o = None
            if not o:
                if reg["tentativas"] >= MAX_TENTATIVAS:
                    reg["status"] = "nao_achou"
                continue
            reg.update({"status": "achado_privado", "achado": {"titulo": o["nome"][:80],
                        "preco_fmt": o["preco_fmt"], "link_afiliado": o["link_afiliado"]}})
            entrou += 1
            print(f"🔒 Pedido sensível de @{reg['usuario']} achado (só no direct).")
            continue
        termo = _refinar(reg)
        termo = reg["termo"] if termo is None else termo
        if not termo:
            reg["status"] = "ignorado"
            continue
        reg["termo"] = termo
        try:
            o = _melhor(shopee.buscar_ofertas(termo, 1, 40, 2), termo, fila)
        except Exception as e:
            print(f"⚠️  Busca do pedido '{termo}' falhou: {e}")
            o = None
        if not o:
            if reg["tentativas"] >= MAX_TENTATIVAS:
                reg["status"] = "nao_achou"
            print(f"🔎 Pedido '{termo}' (@{reg['usuario']}): nada bom o bastante ainda.")
            continue
        o["pedido"] = {"comentario": cid, "usuario": reg["usuario"], "termo": termo}
        o["nivel"], o["uau"], o["pontos"] = "ouro", 8, 999
        texto = legenda.gerar(o)
        corpo, sep, tags = texto["legenda"].partition("\n\n#")
        o["titulo"] = texto["titulo"]
        tags = f"#{tags}" if sep else "#achadinhos #shopee #achados #ofertas #zegarimpo #garimpovip"
        o["legenda"] = f"{cabecalho(o)}\n\n{corpo.strip()}\n\n{CONVITE}\n\n{tags}"
        o.update({"status": "pendente", "criado_em": _agora().strftime(_fmt()), "postado_em": "", "id_post": ""})
        fila["ofertas"][o["id"]] = o
        reg.update({"status": "achado", "oferta": o["id"]})
        entrou += 1
        print(f"🙋 Pedido de @{reg['usuario']} atendido: {termo} → {o['titulo']} (R$ {o['preco_fmt']})")
    salvar(dados)
    return entrou


# ------------------------------------------------------------------ 3) entregar (postar)
def entregar(oferta, ig_id):
    p = oferta.get("pedido")
    if not p:
        return
    from . import instagram
    dados = carregar()
    reg = dados.get(p["comentario"], {})
    texto = (f"Oi! 🤠 Aqui é o Zé Garimpo. Você pediu {p['termo']} e eu achei: {oferta['titulo']} "
             f"por R$ {oferta['preco_fmt']}! Já está no feed do Garimpo VIP. Toque no botão para ver na Shopee 👇\n"
             f"(link de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")
    try:
        instagram.resposta_privada_botao(ig_id, p["comentario"], texto, oferta["link_afiliado"], "🛒 Ver o achado")
        reg["status"] = "entregue"
        print(f"📩 Achado entregue no direct de @{p['usuario']}.")
    except Exception as e:
        reg["entrega"] = f"erro: {str(e)[:200]}"
        print(f"::warning::Não consegui avisar @{p['usuario']} no direct: {e}")
    if reg:
        dados[p["comentario"]] = reg
        salvar(dados)


# ------------------------------------------------------------------ 4) entregar_privados (direct, sem post)
def entregar_privados(ig_id):
    """Manda no direct o achado dos pedidos sensíveis. Nunca aparece no feed nem marca a pessoa."""
    from . import instagram
    dados = carregar()
    limite = (_agora() - timedelta(days=DIAS_JANELA)).strftime(_fmt())
    feitos = 0
    for cid, reg in dados.items():
        if reg.get("status") != "achado_privado":
            continue
        if reg.get("em", "") < limite:   # o Instagram só aceita resposta privada até 7 dias após o comentário
            reg["status"] = "expirado"
            continue
        a = reg["achado"]
        texto = (f"Oi! 🤠 Aqui é o Zé Garimpo. Você pediu {reg['termo']} e eu achei: {a['titulo']} "
                 f"por R$ {a['preco_fmt']}! Toque no botão para ver na Shopee 👇\n"
                 f"(link de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")
        try:
            instagram.resposta_privada_botao(ig_id, cid, texto, a["link_afiliado"], "🛒 Ver o achado")
            reg["status"] = "entregue"
            feitos += 1
            print(f"📩 Pedido sensível entregue no direct de @{reg['usuario']}.")
        except Exception as e:
            reg["entrega"] = f"erro: {str(e)[:200]}"
            print(f"::warning::Não consegui mandar o pedido sensível no direct de @{reg['usuario']}: {e}")
    salvar(dados)
    return feitos
