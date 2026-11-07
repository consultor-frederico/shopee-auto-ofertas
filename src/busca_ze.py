"""🔎 Busca do Zé — post fixo que funciona como ferramenta de busca.

O seguidor comenta o que procura no post fixado (legenda com #BuscaDoZe). Na mesma rodada do
responder (o webhook acorda o robô na hora), o Zé busca na Shopee, AliExpress, Mercado Livre e no catálogo
das lojas oficiais da Awin (04/11/2026), escolhe até 3 achados bons
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
# 04/11/2026 (Fred): o Zé procura em todas as lojas do Garimpo e junta os 3 melhores. A Ana segue só na Shopee.
LOJAS = [l.strip() for l in __import__("os").getenv(
    "BUSCA_LOJAS", "shopee" if ANA else "shopee,mercadolivre,aliexpress,marcas").split(",") if l.strip()]
MAX_POR_LOJA = 2   # dos 3 achados, no máximo 2 da mesma loja (a pessoa vê opções de lugares diferentes)
NOME_LOJA = {"shopee": "Shopee", "aliexpress": "AliExpress", "mercadolivre": "Mercado Livre"}


def _onde(lojas=None):
    """'na Shopee' / 'na Shopee, no Mercado Livre, na AliExpress e nas lojas oficiais'."""
    nomes = {"shopee": "na Shopee", "mercadolivre": "no Mercado Livre", "aliexpress": "na AliExpress",
             "marcas": "nas lojas oficiais"}
    partes = [nomes[l] for l in (lojas or LOJAS) if l in nomes] or ["na Shopee"]
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]

PUBLICAS = ["@{u} o Zé achou! ⛏️ Te mandei no direct 📩",
            "Achei, @{u}! 🤠 Confere o seu direct 📲",
            "@{u} garimpado! ⛏️ Os achados estão no seu direct 💌"]
PUBLICA_NADA = ("@{u} o Zé cavou em todas as lojas e não achou nada bom de \"{t}\" ainda 😅 "
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


PROMPT_SEGUE = """Numa conversa de busca de produtos na Shopee, o cliente tinha pedido "{ant}" e agora escreveu: "{texto}".
Se a mensagem nova só detalha ou corrige o pedido anterior (ex.: "de adulto", "masculino", "tem maior?", "na cor preta",
"mas pra adulto"), junte os dois num termo só (ex.: "roupa motocross" + "consegue de adulto?" → "roupa motocross adulto").
Se ele pediu outro produto, use só o produto novo.
Responda só com JSON {{"produto": "<termo curto de busca na Shopee, 1 a 5 palavras>"}}."""


def _junta_pedido(anterior, texto, novo):
    """2/11/2026 (Allan): "Roupa de motocross" e depois "Consegue roupa de adulto?" era buscado
    como "roupa adulto", sem o motocross. Agora a continuação herda o pedido anterior."""
    import re
    from .legenda import _chamar_groq
    try:
        bruto = _chamar_groq(PROMPT_SEGUE.format(ant=anterior.replace('"', "'"),
                                                 texto=(texto or "")[:200].replace('"', "'")))
        t = str(json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("produto", "")).strip().lower()[:60]
        return t or novo
    except Exception as e:
        print(f"⚠️  IA não juntou com o pedido anterior ({e}); fico com '{novo}'.")
        return novo


def termo(texto, anterior=""):
    """No post fixo todo comentário é uma busca: a IA limpa o texto; sem IA, tira as palavras vazias.
    anterior = o que a mesma pessoa pediu há pouco (a mensagem nova pode ser só um detalhe dele)."""
    from . import pedidos
    if config.GROQ_API_KEY:
        t = pedidos._refinar({"texto": texto, "termo": ""})
        if t is not None:
            return _junta_pedido(anterior, texto, t) if (t and anterior) else t
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
# palavras genéricas do pedido: não precisam estar no nome ("roupa motocross" → "Conjunto Calça Camisa Motocross")
GENERICAS = set("roupa roupinha produto coisa item artigo adulto adulta".split())
# público infantil: se o pedido não fala de criança, esses produtos não servem (2/11/2026, motocross infantil)
INFANTIL = set("infantil infantis crianca criancas kid kids bebe bebes baby menino menina meninos meninas juvenil mirim".split())
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
    pedido = [p for p in pedido if p not in GENERICAS] or pedido
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
        nucleo = re.escape(pedido[0])
        if re.search(rf"\b{PREPOSICOES}\s+(?:o\s+|a\s+|seu\s+|sua\s+)?{nucleo}", _norm(nome)):
            return False                          # "... para celular", "... de celular"
    return True


def _infantil(txt):
    return bool(set(_palavras(txt)) & INFANTIL)


def _plat(o):
    return o.get("plataforma") or "shopee"


def _eh_marca(o):
    from . import marcas
    return marcas.eh_marca(o)


def _aceitavel(o, rigoroso=True):
    nome = o["nome"].lower()
    if not (o["link_afiliado"] and o["imagem"] and 0 < o["preco"] and (not PRECO_MAX or o["preco"] <= PRECO_MAX)
            and not any(p in nome for p in config.PALAVRAS_PROIBIDAS)):
        return False
    if _eh_marca(o):          # loja oficial (Awin): não tem nota nem vendas, a marca é a garantia
        return True
    if _plat(o) == "mercadolivre":   # catálogo do ML não mostra nota/vendas: vale a posição na busca
        return (o.get("posicao") or 99) <= (6 if rigoroso else 12)
    if _plat(o) == "aliexpress":
        from . import aliexpress
        if aliexpress.recusa_extra(o):
            return False
    if rigoroso:
        return o["nota"] >= 4.5 and o["vendas"] >= 50
    return o["nota"] >= 4.3 and o["vendas"] >= 10


PROMPT_IA = """Um cliente pediu numa loja online: "{t}".
Abaixo, produtos encontrados (número: nome — preço). Quais SÃO o próprio produto que ele pediu?
Não conta acessório, peça, capa, suporte, refil, nem produto de outro tipo que só cita a palavra
(ex.: pediu "cama casal" → lençol, colcha ou protetor "para cama casal" NÃO servem; só a cama).
Respeite as características do pedido (adulto ou infantil, masculino ou feminino, tamanho, cor, voltagem):
se ele não pediu infantil/criança, produto infantil NÃO serve; se pediu adulto, só adulto.
Entenda o pedido pelo uso mais comum do produto: "projetor parede" é projetor de imagem/vídeo (de filme,
de ligar no celular), NÃO projetor de estrelas/galáxia, luminária ou luz decorativa; versão de
brinquedo, decorativa ou miniatura só serve se ele pediu assim.
Confira o preço: barato demais para ser o produto de verdade (ex.: "notebook" por R$ 30) é peça,
miniatura ou anúncio enganoso e NÃO serve.{fotos}
Na dúvida, deixe de fora: é melhor mandar 1 produto certo do que 3 errados.
Responda só com JSON {{"ok": [números]}}, do mais adequado para o menos.

{lista}"""
FOTOS_IA = "\nAs fotos vêm na mesma ordem dos números: use a foto para ver o que o produto realmente é."


def _miniatura(url):
    """Foto pequena do produto em base64 (a Shopee serve a miniatura com _tn no fim)."""
    import base64
    import requests
    try:
        if "susercontent.com/file/" in url and not url.endswith("_tn"):
            url += "_tn"
        elif "alicdn.com" in url and url.endswith((".jpg", ".png", ".webp")):
            url += "_220x220.jpg"          # AliExpress: miniatura pelo próprio CDN
        elif "mlstatic.com" in url:
            url = url.replace("-O.", "-I.")   # Mercado Livre: versão pequena da foto
        r = requests.get(url, timeout=10)
        if r.ok and r.content and len(r.content) < 400_000:
            return base64.b64encode(r.content).decode()
    except Exception:
        pass
    return None


def _ia_gemini(t, ofs, lista):
    """Gemini olhando nome, preço e FOTO de cada produto. None se não respondeu."""
    import os
    import re
    import requests
    chave = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not chave:
        return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        fotos = list(ex.map(_miniatura, [o["imagem"] for o in ofs]))
    partes = [{"text": PROMPT_IA.format(t=t.replace('"', "'"), lista=lista, fotos=FOTOS_IA)}]
    for i, f in enumerate(fotos):
        partes.append({"text": f"Foto do produto {i}:"})
        if f:
            partes.append({"inline_data": {"mime_type": "image/jpeg", "data": f}})
        else:
            partes.append({"text": "(sem foto)"})
    import time
    from .radar_virais import _modelos_gemini, config_geracao   # os "flash" que a chave enxerga, do mais novo ao mais velho
    try:
        modelos = [m for m in _modelos_gemini(chave) if "lite" not in m][:4] or ["gemini-2.5-flash"]
    except Exception:
        modelos = ["gemini-2.5-flash"]
    if _ia_usada[1] >= 2:   # o Gemini já falhou 2x nesta rodada (cota grátis acabou): vai direto pro Groq
        return None
    inicio = time.time()
    for modelo in modelos[:3]:   # o plano grátis vive dando 429/503: no máximo ~30 s e segue com o Groq
        if time.time() - inicio > 30:
            break
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                              params={"key": chave}, timeout=25,
                              json={"contents": [{"parts": partes}],
                                    "generationConfig": config_geracao(modelo, 0.1)})
            if r.status_code != 200:
                print(f"⚠️  Gemini {modelo}: HTTP {r.status_code} {' '.join(r.text[:200].split())[:120]}")
                continue
            bruto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            nums = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("ok", [])
            print(f"👁️  Busca conferida pelo Gemini ({modelo}, {sum(1 for f in fotos if f)} fotos).")
            _ia_usada[1] = 0
            _ia_usada[0] = modelo
            return [ofs[int(n)] for n in nums if str(n).isdigit() and int(n) < len(ofs)]
        except Exception as e:
            print(f"⚠️  Gemini {modelo} não conferiu ({str(e)[:100]})")
    _ia_usada[1] += 1
    return None


_ia_usada = ["", 0]   # [IA que conferiu a última busca, falhas seguidas do Gemini nesta rodada]


def _filtro_ia(t, ofs):
    """A IA confere se cada produto é mesmo o pedido: Gemini com as fotos; se falhar, Groq só pelos nomes.
    None se nenhuma IA respondeu."""
    if not ofs:
        return None
    import re
    lista = "\n".join(f"{i}: {o['nome'][:110]} — R$ {o['preco_fmt']}" for i, o in enumerate(ofs))
    _ia_usada[0] = ""
    r = _ia_gemini(t, ofs, lista)
    if r is not None or not config.GROQ_API_KEY:
        return r
    from .legenda import _chamar_groq
    try:
        bruto = _chamar_groq(PROMPT_IA.format(t=t.replace('"', "'"), lista=lista, fotos=""))
        nums = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("ok", [])
        _ia_usada[0] = "groq"
        return [ofs[int(n)] for n in nums if str(n).isdigit() and int(n) < len(ofs)]
    except Exception as e:
        print(f"⚠️  IA não conferiu a busca ({e}); fico só com as regras.")
        return None


def _pontos(o):
    """2/11/2026 (Fred): primeiro o melhor para o cliente (avaliação e vendas = vendedor de confiança);
    entre os confiáveis, a melhor comissão; sem teto de preço.
    04/11/2026: loja oficial vale como vendedor de confiança (nota 4,8 e 2.000 vendas); no Mercado Livre,
    que não mostra nota nem vendas, o 1º da busca vale 3.000 vendas, o 2º 1.500, o 3º 1.000...
    e do 4º em diante só "confiável"."""
    if _eh_marca(o):
        return (True, True, 2000 * 4.8 + o["comissao"] * 30)
    if _plat(o) == "mercadolivre":
        pos = o.get("posicao") or 99
        return (pos <= 3, True, 3000 / pos * 4.8 + o["comissao"] * 30)
    confiavel = o["nota"] >= 4.7 and o["vendas"] >= 100
    return (o["nota"] >= 4.8 and o["vendas"] >= 100, confiavel and o["comissao"] >= 3,
            min(o["vendas"], 5000) * o["nota"] + o["comissao"] * 30)


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


def _da_shopee(t):
    from . import shopee
    from .garimpar import normalizar
    nos = []
    sem_genericas = " ".join(p for p in t.split() if _raiz(_norm(p)) not in GENERICAS)
    buscas = [t] + ([sem_genericas] if sem_genericas and sem_genericas != t else [])
    for busca in buscas:   # "roupa motocross adulto" também busca "motocross" (vendedor não escreve "roupa")
        for pagina, ordem in ((1, 1), (2, 1), (1, 2)):
            for tentativa in (1, 2, 3):   # a Shopee às vezes devolve "System Error" (10000) e na hora seguinte funciona
                try:
                    nos += shopee.buscar_ofertas(busca, pagina, 50, ordem)
                    break
                except Exception as e:
                    print(f"⚠️  Shopee '{busca}' (página {pagina}, ordem {ordem}, tentativa {tentativa}): {str(e)[:100]}")
                    if "10000" not in str(e) or tentativa == 3:
                        break
                    import time
                    time.sleep(2 * tentativa)
    return [normalizar(n, "busca", t) for n in nos]


def _da_aliexpress(t):
    from . import aliexpress
    if not aliexpress.configurado():
        return []
    nos = []
    for ordem in ("LAST_VOLUME_DESC", "SALE_PRICE_ASC"):
        try:
            nos += aliexpress.buscar_produtos(t, 1, ordem, 50)
        except Exception as e:
            print(f"⚠️  AliExpress '{t}' ({ordem}): {str(e)[:100]}")
    return [aliexpress.normalizar(p, "busca", t) for p in nos]


def _das_marcas(t):
    """Catálogo das lojas oficiais (Awin). A Arno tem feed parado: preço e estoque conferidos na loja."""
    from . import awin, marcas
    if not awin.configurado():
        return []
    ofs = [dict(o, palavra=t) for o in awin.produtos() if relevante(o["nome"], t)]
    ofs.sort(key=lambda o: (o.get("desconto") or 0, o["comissao"]), reverse=True)
    saida = []
    for o in ofs:
        if len(saida) >= 3:
            break
        if marcas.MARCAS.get(o["plataforma"], {}).get("conferir_site") and awin._conferir_site(o) in ("sumiu", "erro"):
            continue
        saida.append(o)
    return saida


def _do_mercadolivre(t):
    from . import mercadolivre
    if not mercadolivre.configurado():
        return []
    return mercadolivre.buscar(t, quantos=12)


FONTES = {"shopee": _da_shopee, "aliexpress": _da_aliexpress, "marcas": _das_marcas,
          "mercadolivre": _do_mercadolivre}
POR_LOJA_NA_IA = {"shopee": 12, "aliexpress": 5, "marcas": 3, "mercadolivre": 6}   # quantos de cada loja a IA confere


def _buscar_lojas(t, lojas):
    """Busca nas lojas ao mesmo tempo. Uma loja que falhar fica de fora, as outras seguem."""
    from concurrent.futures import ThreadPoolExecutor
    lojas = [l for l in lojas if l in FONTES]
    if "mercadolivre" in lojas:   # pega o token antes das buscas paralelas
        try:
            from . import mercadolivre
            if mercadolivre.configurado():
                mercadolivre.access_token()
        except Exception as e:
            print(f"⚠️  Mercado Livre fora desta busca: {str(e)[:120]}")
            lojas.remove("mercadolivre")

    def roda(loja):
        try:
            return FONTES[loja](t)
        except Exception as e:
            print(f"⚠️  {NOME_LOJA.get(loja, loja)} falhou na busca '{t}': {str(e)[:120]}")
            return []
    with ThreadPoolExecutor(len(lojas) or 1) as ex:
        return dict(zip(lojas, ex.map(roda, lojas)))


def _loja(o):
    return "marcas" if _eh_marca(o) else _plat(o)


def achados(t, lojas=None):
    """Até 3 produtos que SÃO o que a pessoa pediu, juntando as lojas (Shopee, Mercado Livre, AliExpress e
    lojas oficiais): busca por relevância (e mais vendidos), regras contra acessórios, e a IA confere a lista final."""
    lojas = list(lojas or LOJAS)
    por_loja = _buscar_lojas(t, lojas)
    vistos, unicos = set(), []
    for o in (o for ofs in por_loja.values() for o in ofs):
        if o["id"] not in vistos:
            vistos.add(o["id"])
            unicos.append(o)
    certos = [o for o in unicos if relevante(o["nome"], t)]
    if not _infantil(t):   # pediu "roupa motocross" (ou "de adulto"): nada de roupa de criança
        certos = [o for o in certos if not _infantil(o["nome"])]
    contagem = {l: len(v) for l, v in por_loja.items()}
    for rigoroso in (True, False):
        bons = []
        for loja in lojas:   # os melhores de cada loja vão para a IA conferir juntos
            da_loja = sorted((o for o in certos if _loja(o) == loja and _aceitavel(o, rigoroso)), key=_pontos, reverse=True)
            bons += da_loja[:POR_LOJA_NA_IA.get(loja, 5)]
        if not bons:
            continue
        print(f"🛒 '{t}': encontrados {contagem}, para conferir {[(l, sum(1 for o in bons if _loja(o) == l)) for l in lojas]}")
        bons.sort(key=_pontos, reverse=True)
        conferidos = _filtro_ia(t, bons)
        if conferidos is not None:   # a IA decide o que serve; a ordem continua a da qualidade
            bons = sorted(conferidos, key=_pontos, reverse=True)
        bons = _sem_repetidos(bons)   # mesmo produto em duas lojas: fica o mais barato
        escolhidos, n_loja = [], {}
        for o in bons:
            if n_loja.get(_loja(o), 0) < MAX_POR_LOJA:
                escolhidos.append(o)
                n_loja[_loja(o)] = n_loja.get(_loja(o), 0) + 1
        if escolhidos:
            return escolhidos[:ACHADOS]
    return []


def _resumo(ofs):
    """O que foi mandado, para a revisão (python -m src.busca_ze revisar)."""
    return {"enviados": [f"{_nome_loja(o)} | {o['nome'][:90]} | R$ {o['preco_fmt']} | {_selo(o, True)} | "
                         f"com. R$ {o['comissao']:.2f}" for o in ofs], "ia": _ia_usada[0] or "regras"}


def _nome_loja(o):
    from . import marcas
    return f"{marcas.nome(o)} oficial" if _eh_marca(o) else NOME_LOJA.get(_plat(o), _plat(o))


def _selo(o, interno=False):
    """O que garante o achado: nota e vendas; loja oficial; no Mercado Livre, frete grátis/Full (e, só no
    relatório, a posição na busca)."""
    if _eh_marca(o):
        return "loja oficial"
    if _plat(o) == "mercadolivre":
        extras = [x for x, ok in (("frete grátis", o.get("frete_gratis")), ("Full", o.get("full"))) if ok]
        return ", ".join(([f"{o.get('posicao')}º na busca"] if interno else []) + extras) or "Mercado Livre"
    vendas_txt = f"{o['vendas']:,}".replace(",", ".")
    nota = f"{o['nota']:.1f}".replace(".", ",")
    return f"⭐ {nota}, {vendas_txt}+ vendidos"


def _curto(nome, n=45):
    nome = " ".join(nome.split())
    return nome if len(nome) <= n else nome[:n - 1].rstrip() + "…"


def mensagem(t, ofs):
    linhas = [(f"Oi! 💚 Aqui é a Ana. Procurei \"{t}\" {_onde()} e separei pra você:" if ANA
               else f"Oi! 🤠 Aqui é o Zé Garimpo. Garimpei \"{t}\" {_onde()} e separei os melhores:"), ""]
    varias = len(LOJAS) > 1
    for i, o in enumerate(ofs, 1):
        intl = " 🌎 internacional" if o.get("internacional") else ""
        selo = _selo(o)
        loja = _nome_loja(o) if _eh_marca(o) or not varias or selo == "Mercado Livre" else f"{_nome_loja(o)} • "
        selo = "" if _eh_marca(o) or selo == "Mercado Livre" else selo
        linhas.append(f"{i}️⃣ {_curto(o['nome'])} — R$ {o['preco_fmt']} ({loja}{selo}){intl}")
    if config.PAGINA_BIO:
        linhas += ["", f"🔗 Os outros achados de hoje: {config.PAGINA_BIO}"]
    linhas += ["", "Toque no botão do que gostou 👇",
               (AVISO_ANA if ANA else f"(links de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")]
    return "\n".join(linhas)


def _cartao(i, o):
    """Um achado em cartão (template genérico): foto, nome, preço/nota/vendas e os botões."""
    link = vendas.do_canal(o, "zebusca")
    intl = " • internacional" if o.get("internacional") else ""
    loja = f"{_nome_loja(o)} • " if len(LOJAS) > 1 or _plat(o) != "shopee" else ""
    selo = "" if _eh_marca(o) or _selo(o) == "Mercado Livre" else f" • {_selo(o).replace(', ', ' • ')}"
    botoes = [{"type": "web_url", "url": link, "title": f"🛒 Ver achado {i}"}]
    if config.PAGINA_BIO:
        botoes.append({"type": "web_url", "url": f"https://{config.PAGINA_BIO}", "title": "🔗 Achados de hoje"})
    return {"title": f"{i}. {_curto(o['nome'], 70)}",
            "subtitle": f"{loja}R$ {o['preco_fmt']}{selo}{intl} • link de afiliado"[:80],
            "image_url": o["imagem"], "default_action": {"type": "web_url", "url": link}, "buttons": botoes}


def enviar_dm(api, ig_id, cid, t, ofs, destinatario=None):
    """Manda os achados no direct: como resposta privada a um comentário (cid) ou,
    numa conversa que a pessoa abriu, direto para ela (destinatario = id da pessoa)."""
    para = {"id": destinatario} if destinatario else {"comment_id": cid}
    texto = mensagem(t, ofs)
    try:   # 31/10/2026 (Fred): cartões com foto, lado a lado, cada um com o botão do achado e o da vitrine da bio
        return api._req("POST", f"{ig_id}/messages", json={
            "recipient": para,
            "message": {"attachment": {"type": "template", "payload": {
                "template_type": "generic", "elements": [_cartao(i, o) for i, o in enumerate(ofs, 1)]}}}})
    except Exception as e:   # uma tentativa recusada não gasta a resposta privada
        print(f"⚠️  Cartões recusados ({e}); mandando com botões.")
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
DM_NADA = ("Oi! 🤠 Aqui é o Zé Garimpo. Cavei \"{t}\" em todas as lojas, mas não achei nada bom o bastante 😅 "
           "Me manda com outras palavras (ex.: \"fone bluetooth\", \"air fryer 5 litros\") que eu tento de novo!")
if ANA:
    DM_NADA = ("Oi! 💚 Aqui é a Ana. Procurei \"{t}\" na Shopee, mas não achei nada bom o bastante 😕 "
               "Me manda com outras palavras (ex.: \"bolsa transversal\", \"escova secadora\") que eu tento de novo!")
# depois dos achados no direct: confere se era isso (a resposta em até 30 min se junta ao pedido)
DM_CONFERE = ("Oi! 🤠 Era isso que você procurava? Se não for, me conta com mais detalhe "
              "(ex.: adulto ou infantil, tamanho, cor, modelo) que eu garimpo de novo! ⛏️")
if ANA:
    DM_CONFERE = ("Oi! 💚 Era isso que você procurava? Se não for, me conta com mais detalhe "
                  "(tamanho, cor, modelo...) que eu procuro de novo pra você!")
DM_OBRIGADO = ("Oi! 🤠 Eu que agradeço! Fico feliz que o Zé acertou ⛏️ Quando quiser outro achado, "
               "é só me mandar o nome do produto aqui que eu garimpo pra você 😉")
DM_DETALHE = ("Oi! 🤠 Poxa, foi mal! Me conta com mais detalhe o que você procura "
              "(ex.: adulto ou infantil, tamanho, cor, modelo, pra que vai usar) que eu garimpo de novo ⛏️")
if ANA:
    DM_OBRIGADO = ("Oi! 💚 Imagina, amiga! Que bom que gostou! Quando quiser outro achadinho, é só me mandar aqui 😉")
    DM_DETALHE = ("Oi! 💚 Ah, poxa! Me conta com mais detalhe o que você procura (tamanho, cor, modelo...) "
                  "que eu procuro de novo pra você!")
# "quero" solto no direct (sem dizer qual achado): pergunta qual; a resposta vira busca ("Bora garimpar")
DM_QUAL = ("Oi! 🤠 Aqui é o Zé Garimpo. Bora garimpar! ⛏️\n\nQual achado você quer? Me manda o nome do produto "
           "(ex.: \"câmera wi-fi\", \"kit lavabo\") que eu te mando o link aqui.\n\n"
           "Dica: comentando QUERO no post, o link chega sozinho no direct 😉")
if ANA:
    DM_QUAL = ("Oi, amiga! 💚 Bora garimpar? Qual achado você quer? Me manda o nome do produto "
               "(ex.: \"bolsa transversal\", \"escova secadora\") que eu te mando o link aqui.\n\n"
               "Dica: comentando QUERO no post, o link chega sozinho no direct 😉")


def _avisar_fred(reg, quando):
    """Mensagem do direct que o robô não respondeu → alerta no Telegram privado do Fred."""
    import os
    import requests   # direto na API (o src.telegram puxa o Pillow, que o workflow 3 não instala)
    from . import direct_telegram
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not (chat and token):
        return
    ate = (quando + timedelta(hours=24)).strftime("%d/%m %H:%M")
    quem = f"@{reg['usuario']}" if reg.get("usuario") else "alguém"
    texto = (f"📩 Direct do {config.ARROBA} sem resposta do robô\n\n"
             f"{quem}: \"{(reg.get('texto') or '')[:300]}\"\n\nResponda até {ate} (depois o Instagram fecha a conversa).\n"
             "Para responder por aqui: segure esta mensagem → Responder → escreva. Eu mando no direct.\n\n"
             + direct_telegram.ref(config.PERFIL, reg["autor"]))
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=30,
                          data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"})
        if not r.json().get("ok"):
            raise RuntimeError(r.text[:200])
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
                               "os 3 melhores achados da Shopee, do Mercado Livre e das outras lojas."
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
        conferiu = ((anterior.get("from") or {}).get("id") == ig_id
                    and "Era isso que você procurava" in (anterior.get("message") or ""))
        # resposta ao "Era isso que você procurava?" continua a mesma busca, mesmo horas depois
        anterior_t = _pedido_recente(feitos_ids, autor, agora, JANELA_DM if conferiu else SEGUE_PEDIDO)
        t = termo(texto, anterior_t) if (acabou_de_perguntar or config.GROQ_API_KEY) else pedidos._termo(texto)
        if not t and not conferiu and _parece_modelo(texto):   # 7/11/2026 (Bruno: "S25" no story ficou sem resposta)
            t = _norm(texto).strip(" ?!.")
        reg = {"autor": autor, "usuario": (ultima.get("from") or {}).get("username", ""), "texto": texto,
               "termo": t, "em": agora.strftime(_fmt())}
        if not t and conferiu:   # 2/11/2026 (Allan: "Sim obrigado" ficou sem resposta)
            resposta = DM_DETALHE if _negou(texto) else DM_OBRIGADO
            try:
                r = api._req("POST", f"{ig_id}/messages", json={"recipient": {"id": autor},
                                                                "message": {"text": resposta}})
                if (r or {}).get("message_id"):
                    enviados_robo.add(r["message_id"])
                reg["status"] = "pediu_detalhe" if resposta == DM_DETALHE else "agradeceu"
                feitos += 1
                print(f"📩 Direct: resposta ao \"era isso?\" → {reg['status']}.")
            except Exception as e:
                reg["status"] = f"erro: {str(e)[:200]}"
                print(f"::warning::Direct: não consegui responder o \"era isso?\": {e}")
                _avisar_fred(reg, quando)
            feitos_ids[ultima["id"]] = reg
            continue
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
                    _avisar_fred(reg, quando)
            else:
                reg["status"] = "ignorado"
                _avisar_fred(reg, quando)
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
                reg.update({"status": "entregue", "achados": [o["id"] for o in ofs], **_resumo(ofs)})
                try:   # 2/11/2026 (Fred): o Zé confere se acertou; a resposta vira detalhe da mesma busca
                    c = api._req("POST", f"{ig_id}/messages", json={"recipient": {"id": autor},
                                                                    "message": {"text": DM_CONFERE}})
                    if (c or {}).get("message_id"):
                        enviados_robo.add(c["message_id"])
                except Exception as e:
                    print(f"⚠️  Não mandei a pergunta de conferência: {e}")
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
            _avisar_fred(reg, quando)
        feitos_ids[ultima["id"]] = reg
    limite = (agora - timedelta(days=30)).strftime(_fmt())
    d["dms"] = {k: v for k, v in feitos_ids.items() if v.get("em", "") >= limite}
    d["msgs_robo"] = list(enviados_robo)[-300:]
    salvar(d)
    return feitos


def _parece_modelo(texto):
    """Mensagem curta que é só um modelo de produto ("S25", "iphone 15", "ps5", "rtx 4060")."""
    import re
    t = _norm(texto).strip(" ?!.")
    return (len(t.split()) <= 3 and len(t) <= 25 and bool(re.search(r"[a-z]", t)) and bool(re.search(r"\d", t))
            and not re.search(r"\b(r\$|reais|real|kg|dia|dias|hora|horas|h)\b", t))


SEGUE_PEDIDO = timedelta(minutes=30)   # mensagem nova até 30 min depois de uma busca pode ser detalhe dela


def _negou(texto):
    """'não', 'não era', 'errado' (sem dizer o que quer) → pede mais detalhe."""
    import re
    return bool(re.search(r"\b(nao|n|errad[oa]|nada a ver|outr[oa])\b", _norm(texto)))


def _pedido_recente(feitos, autor, agora, janela=None):
    """O último termo que essa pessoa buscou no direct, se foi há pouco ("" se não tem)."""
    limite = (agora - (janela or SEGUE_PEDIDO)).strftime(_fmt())
    regs = [v for v in feitos.values() if v.get("autor") == autor and v.get("termo") and v.get("em", "") >= limite
            and v.get("status") in ("entregue", "nao_achou")]
    return max(regs, key=lambda v: v["em"])["termo"] if regs else ""


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
                reg.update({"status": "entregue", "achados": [o["id"] for o in ofs], **_resumo(ofs)})
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
    if sys.argv[1:2] == ["revisar"]:   # buscas dos últimos N dias (padrão 7), com o que foi mandado
        dias = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        lim = (_agora() - timedelta(days=dias)).strftime(_fmt())
        d = carregar()
        regs = [dict(v, onde="direct") for v in d.get("dms", {}).values()] + \
               [dict(v, onde="comentário") for v in d.get("comentarios", {}).values()]
        for v in sorted((v for v in regs if v.get("em", "") >= lim and v.get("termo")), key=lambda v: v["em"]):
            print(f"\n{v['em']} @{v.get('usuario', '?')} ({v['onde']}): {v.get('texto', '')[:80]!r} → "
                  f"\"{v['termo']}\" [{v.get('status')}, IA: {v.get('ia', '?')}]")
            for e in v.get("enviados", []):
                print(f"   • {e}")
        sys.exit(0)
    if sys.argv[1:2] == ["enviar"]:   # python -m src.busca_ze enviar <@ de quem buscou no direct> <termo> [intro]
        from . import instagram
        usuario, t = sys.argv[2].lstrip("@").lower(), sys.argv[3].strip()
        intro = (sys.argv[4] if len(sys.argv) > 4 else "").strip()
        ig = instagram.conferir_conta()["user_id"]
        d = carregar()
        regs = [v for v in d.get("dms", {}).values() if (v.get("usuario") or "").lower() == usuario]
        if not regs:
            sys.exit(f"::error::Não achei busca de @{usuario} no direct. Nada foi enviado.")
        autor = max(regs, key=lambda v: v["em"])["autor"]
        ofs = achados(t)
        if not ofs:
            sys.exit(f"::error::Nada bom para '{t}'. Nada foi enviado.")
        if intro:
            instagram._req("POST", f"{ig}/messages", json={"recipient": {"id": autor}, "message": {"text": intro}})
        enviar_dm(instagram, ig, None, t, ofs, destinatario=autor)
        instagram._req("POST", f"{ig}/messages", json={"recipient": {"id": autor}, "message": {"text": DM_CONFERE}})
        for o in ofs:
            print(f"::notice::Enviado a @{usuario}: {_nome_loja(o)} R$ {o['preco_fmt']} {_selo(o, True)} — {o['nome'][:80]}")
        d["dms"][f"manual-{_agora().strftime('%Y%m%d%H%M%S')}"] = {
            "autor": autor, "usuario": usuario, "texto": "(envio manual)", "termo": t, "em": _agora().strftime(_fmt()),
            "status": "entregue", "achados": [o["id"] for o in ofs], **_resumo(ofs)}
        salvar(d)
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
        t = t.strip()
        ant, _, t = t.rpartition(">")   # "roupa de motocross > consegue de adulto?" = conversa com 2 mensagens
        ant = (termo(ant.strip()) or ant.strip()) if ant else ""
        busca = termo(t.strip(), ant) or t.strip()
        print(f"\n🔎 {t.strip()}" + (f"  (antes: {ant})" if ant else "") + f"  → busca \"{busca}\"")
        try:
            for o in achados(busca):
                print(f"  • {_nome_loja(o):<14} R$ {o['preco_fmt']:>9} {_selo(o, True):<28} — {o['nome'][:80]}")
        except Exception as e:
            print(f"  ⚠️  {e}")
