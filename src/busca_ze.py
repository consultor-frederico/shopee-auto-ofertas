"""🔎 Busca do Zé — post fixo que funciona como ferramenta de busca.

O seguidor comenta o que procura no post fixado (legenda com #BuscaDoZe). Na mesma rodada do
responder (o webhook acorda o robô na hora), o Zé busca na Shopee, escolhe até 3 achados bons
e manda no direct da pessoa (resposta privada ao comentário, com um botão por achado).
No comentário, responde em público: "Te mandei no direct!".

Vale para todo post com #BuscaDoZe na legenda: a foto fixada e os Reels do rodízio (src/busca_reels.py). A limpeza de
15 dias não o apaga, porque ela só mexe nos posts que o robô registrou.
"""
import json
from datetime import timedelta

from . import config

ARQ = config.PASTA_PERFIL / "busca_ze.json"
TAG = "buscadoze"
MAX_POR_RODADA = 15
ACHADOS = 3

PUBLICAS = ["@{u} o Zé achou! ⛏️ Te mandei no direct 📩",
            "Achei, @{u}! 🤠 Confere o seu direct 📲",
            "@{u} garimpado! ⛏️ Os achados estão no seu direct 💌"]
PUBLICA_NADA = ("@{u} o Zé cavou, cavou e não achou nada bom de \"{t}\" ainda 😅 "
                "Tenta com outras palavras (ex.: \"fone bluetooth\")!")


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
    return list(ids)


def termo(texto):
    """No post fixo todo comentário é uma busca: a IA limpa o texto; sem IA, tira as palavras vazias."""
    from . import pedidos
    if config.GROQ_API_KEY:
        t = pedidos._refinar({"texto": texto, "termo": ""})
        if t is not None:
            return t
    return pedidos.termo_do_comentario(texto, exigir_pedido=False)


PRECO_MAX = float(__import__("os").getenv("BUSCA_PRECO_MAX", "5000"))   # quem pede celular quer celular
ACESSORIOS = set("""capa capinha case pelicula peliculas protetor protecao carregador carregadores cabo cabos
suporte suportes tomada adaptador adaptadores refil refis pecas peca reposicao kit kits bolsa bolsinha estojo
porta organizador adesivo adesivos skin skins alca cordao chaveiro tampa tampas filtro filtros escova escovas
lente lentes bateria baterias fonte controle capas""".split())
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
    if not (set(pedido) & ACESSORIOS):          # pediu o produto, não um acessório
        if set(nome_p[:4]) & ACESSORIOS:         # nome começa com o acessório ("Capa ... celular")
            return False
        nucleo = re.escape(_palavras(t)[0])
        if re.search(rf"\b{PREPOSICOES}\s+(?:o\s+|a\s+|seu\s+|sua\s+)?{nucleo}", _norm(nome)):
            return False                          # "... para celular", "... de celular"
    return True


def _aceitavel(o, rigoroso=True):
    nome = o["nome"].lower()
    if not (o["link_afiliado"] and o["imagem"] and 0 < o["preco"] <= PRECO_MAX
            and not any(p in nome for p in config.PALAVRAS_PROIBIDAS)):
        return False
    if rigoroso:
        return o["nota"] >= 4.5 and o["vendas"] >= 30
    return o["nota"] >= 4.3 and o["vendas"] >= 5


PROMPT_IA = """Um cliente pediu na Shopee: "{t}".
Abaixo, produtos encontrados (número: nome). Quais SÃO o próprio produto que ele pediu?
Não conta acessório, peça, capa, suporte, refil, nem produto de outro tipo que só cita a palavra.
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
        if bons:
            return bons[:ACHADOS]
    return []


def _curto(nome, n=45):
    nome = " ".join(nome.split())
    return nome if len(nome) <= n else nome[:n - 1].rstrip() + "…"


def mensagem(t, ofs):
    linhas = [f"Oi! 🤠 Aqui é o Zé Garimpo. Garimpei \"{t}\" na Shopee e separei:", ""]
    for i, o in enumerate(ofs, 1):
        vendas = f"{o['vendas']:,}".replace(",", ".")
        nota = f"{o['nota']:.1f}".replace(".", ",")
        linhas.append(f"{i}️⃣ {_curto(o['nome'])} — R$ {o['preco_fmt']} (⭐ {nota}, {vendas}+ vendidos)")
    linhas += ["", "Toque no botão do que gostou 👇",
               f"(links de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})"]
    return "\n".join(linhas)


def enviar_dm(api, ig_id, cid, t, ofs):
    texto = mensagem(t, ofs)
    botoes = [{"type": "web_url", "url": o["link_afiliado"], "title": f"🛒 Ver achado {i}"}
              for i, o in enumerate(ofs, 1)]
    try:
        api._req("POST", f"{ig_id}/messages", json={
            "recipient": {"comment_id": cid},
            "message": {"attachment": {"type": "template", "payload": {
                "template_type": "button", "text": texto[:640], "buttons": botoes}}}})
    except Exception as e:   # plano B: texto com os links
        print(f"⚠️  Botões recusados ({e}); mandando os links no texto.")
        links = "\n".join(f"{i}️⃣ {o['link_afiliado']}" for i, o in enumerate(ofs, 1))
        api.resposta_privada(ig_id, cid, f"{texto.split('Toque no botão')[0].strip()}\n\n{links}\n\n"
                                         f"(links de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")


def rodar(api, minha, ja_respondidos=None):
    """Atende os comentários novos do post fixo. Devolve quantas buscas entregou."""
    if config.PERFIL != "garimpo":
        return 0
    d = carregar()
    ig_id = minha["user_id"]
    coms = []
    for post in posts_da_busca(api, ig_id, d):
        falhas = d.setdefault("falhas", {})
        try:
            coms += api.comentarios(post)
            falhas.pop(post, None)
        except Exception as e:   # post apagado (ex.: Reels antigo do rodízio): sai da lista após 3 erros seguidos
            falhas[post] = falhas.get(post, 0) + 1
            print(f"⚠️  Busca do Zé: post {post} indisponível ({e}) — tentativa {falhas[post]}/3.")
            if falhas[post] >= 3:
                d["ids"].remove(post)
                falhas.pop(post)
    feitos = 0
    for c in coms:
        cid, autor = c["id"], (c.get("from") or {}).get("id")
        if cid in d["comentarios"] or autor == ig_id or c.get("username") == minha.get("username"):
            continue
        if feitos >= MAX_POR_RODADA:
            break
        usuario = c.get("username") or (c.get("from") or {}).get("username", "")
        texto = c.get("text", "")
        reg = {"usuario": usuario, "autor": autor, "texto": texto, "em": _agora().strftime(_fmt())}
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
    for t in sys.argv[1:] or ["celular"]:
        print(f"\n🔎 {t}")
        try:
            for o in achados(termo(t) or t):
                print(f"  • R$ {o['preco_fmt']:>9} ⭐{o['nota']} {o['vendas']:>6} vend. — {o['nome'][:90]}")
        except Exception as e:
            print(f"  ⚠️  {e}")
