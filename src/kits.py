"""🧺 Kits do Zé — carrossel temático ("Banheiro organizado", "Amigo secreto até R$ 50"...) em vez de "achados de hoje".

Cada kit tem um tema com 5 a 6 buscas na Shopee (uma por item do kit). De cada busca sai o melhor produto que É o
que foi buscado (regras da Busca do Zé + IA conferindo), com nota, vendas e comissão mínimas e o teto de preço do tema.
Post que dá vontade de salvar e mandar para alguém: capa com o tema e as fotos, depois os produtos numerados
(QUERO 2 → link do 2º, pelo mesmo registro do Top 5 em data/<perfil>/top.json) e o slide final.

Uso:
  python -m src.kits preparar [tema]   → escolhe o tema da vez (ou o pedido) e gera os slides em site/midia/kits/
  python -m src.kits publicar          → publica no Instagram (e na Página do Facebook) e registra para o QUERO N
  python -m src.kits previa [tema|todos] → só gera os slides em data/relatorios/kits/ (não posta)
"""
import json
import os
import re
import shutil
import sys
import time
from datetime import timedelta

from PIL import Image, ImageDraw, ImageOps

from . import config, imagem, instagram, numeros, tiktok_kit
from .garimpar import FMT, agora, carregar_fila, normalizar, salvar_fila

ANA = config.PERFIL == "ana"
L, A = 1080, 1350
QTD = 5
MINIMO = 4
PASTA_SITE = config.RAIZ / "site"
ARQ_ESTADO = config.PASTA_PERFIL / "kits.json"
ARQ_PROXIMO = config.PASTA_PERFIL / "kits_proximo.json"
ARQ_TOP = config.PASTA_PERFIL / "top.json"
NUM = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

# Curadoria do kit: as regras de sempre, com vendas e comissão em R$ mais baixas, porque item de kit costuma ser
# barato (um porta-escova de R$ 25 nunca paga R$ 5). O teto de preço é o de cada tema.
KIT_NOTA = config.NOTA_MINIMA
KIT_VENDAS = int(os.getenv("KIT_VENDAS", "300"))
KIT_COMISSAO_PCT = float(os.getenv("KIT_COMISSAO_PCT", "8"))
KIT_COMISSAO_RS = float(os.getenv("KIT_COMISSAO_RS", "2"))

# meses = em que meses o tema pode sair (vazio = o ano todo). Os de festa têm prioridade no mês deles.
TEMAS = {
    "banheiro": {"titulo": "BANHEIRO ORGANIZADO", "teto": 80, "meses": [],
                 "gancho": "Seu banheiro organizado com {n} achados até R$ {teto}",
                 "termos": ["organizador pia banheiro", "dispenser sabonete", "porta escova de dente",
                            "prateleira canto box", "tapete antiderrapante banheiro", "toalheiro adesivo",
                            "cesto de roupa", "porta shampoo parede", "lixeira banheiro"],
                 "hashtags": "#banheiroorganizado #organizacaodecasa #achadinhosdecasa"},
    "cozinha": {"titulo": "COZINHA PRÁTICA", "teto": 80, "meses": [],
                "gancho": "Cozinha prática: {n} achados até R$ {teto} que facilitam o dia a dia",
                "termos": ["organizador de geladeira", "fatiador de legumes", "porta tempero giratório",
                           "escorredor de louça dobrável", "mini processador elétrico", "pote hermético",
                           "dispenser de detergente", "suporte papel toalha"],
                "hashtags": "#cozinhapratica #utensiliosdecozinha #achadinhosdecasa"},
    "amigo-secreto": {"titulo": "AMIGO SECRETO ATÉ R$ 50", "teto": 50, "meses": [11, 12],
                      "gancho": "Amigo secreto até R$ 50: {n} presentes que ninguém vai querer trocar",
                      "termos": ["caneca térmica", "luminária criativa", "umidificador de ar", "garrafa térmica",
                                 "massageador de pescoço", "caixa de som bluetooth",
                                 "kit vinho", "copo térmico"],
                      "hashtags": "#amigosecreto #presentecriativo #ideiasdepresente"},
    "natal": {"titulo": "PRESENTES DE NATAL", "teto": 120, "meses": [11, 12],
              "gancho": "Presentes de Natal até R$ {teto}: {n} ideias pra riscar da lista",
              "termos": ["projetor de galáxia", "massageador elétrico", "fone bluetooth", "kit ferramentas",
                         "luminária de lua", "mini câmera instantânea",
                         "relógio digital despertador", "kit churrasco"],
              "hashtags": "#presentedenatal #natal #ideiasdepresente"},
    "festa": {"titulo": "FESTA DE FIM DE ANO", "teto": 80, "meses": [11, 12],
              "gancho": "Festa de fim de ano: {n} achados até R$ {teto} pra deixar tudo pronto",
              "termos": ["cortina de led", "pisca pisca led", "taça acrílico", "balde de gelo",
                         "toalha de mesa natal", "enfeite de natal",
                         "luminária de natal", "porta guardanapo"],
              "hashtags": "#festadefimdeano #decoracaodenatal #ceiadenatal"},
    "pet": {"titulo": "KIT DO PET", "teto": 80, "meses": [],
            "gancho": "Kit do pet: {n} achados até R$ {teto} pro seu bichinho",
            "termos": ["fonte bebedouro gato", "removedor de pelos", "comedouro elevado",
                       "brinquedo interativo gato", "cama pet", "escova para cachorro",
                       "arranhador gato", "guia retrátil"],
            "hashtags": "#petlovers #cachorro #gato"},
    "carro": {"titulo": "CARRO EM ORDEM", "teto": 80, "meses": [],
              "gancho": "Carro em ordem: {n} achados até R$ {teto} pra quem vive no trânsito",
              "termos": ["organizador banco carro", "aspirador automotivo", "suporte celular carro",
                         "lixeira para carro", "kit limpeza automotiva", "carregador veicular",
                         "organizador porta malas", "protetor solar parabrisa"],
              "hashtags": "#acessoriosautomotivos #carro #dicasdecarro"},
    "home-office": {"titulo": "HOME OFFICE", "teto": 100, "meses": [],
                    "gancho": "Home office: {n} achados até R$ {teto} pra trabalhar melhor em casa",
                    "termos": ["suporte para notebook", "luminária de mesa led", "organizador de mesa",
                               "mouse pad grande", "apoio para os pés", "suporte de monitor",
                               "organizador de cabos", "luminária usb"],
                    "hashtags": "#homeoffice #escritorioemcasa #setup"},
}


def _saida(chave, valor):
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"{chave}={valor}\n")


def _carregar_estado():
    if ARQ_ESTADO.exists():
        return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
    return {"temas": {}}


def tema_da_vez():
    """Tema de festa do mês primeiro (o que saiu há mais tempo), depois os do ano todo; nunca o mesmo duas vezes seguidas."""
    usados = _carregar_estado()["temas"]
    mes = agora().month
    ultimo = max(usados, key=usados.get) if usados else None
    festa = [t for t, c in TEMAS.items() if mes in c["meses"] and t != ultimo]
    sempre = [t for t, c in TEMAS.items() if not c["meses"] and t != ultimo]
    # nos meses de festa, 2 de cada 3 kits são de festa
    n_festa = sum(1 for t in sorted(usados, key=usados.get)[-3:] if TEMAS.get(t, {}).get("meses"))
    lista = (festa if festa and n_festa < 2 else sempre) or festa or list(TEMAS)
    return min(lista, key=lambda t: usados.get(t, ""))


# ---------------------------------------------------------------- produtos
def _postado_recente(fila, item_id):
    reg = fila["ofertas"].get(item_id) or {}
    if reg.get("status") != "postado" or not reg.get("postado_em"):
        return False
    return reg["postado_em"] >= (agora() - timedelta(days=config.DIAS_SEM_REPETIR)).strftime(FMT)


def _passa(o, teto, fila):
    from . import variedade
    nome = o["nome"].lower()
    return (o["link_afiliado"] and o["imagem"] and 0 < o["preco"] <= teto
            and o["nota"] >= KIT_NOTA and o["vendas"] >= KIT_VENDAS
            and o["comissao_pct"] >= KIT_COMISSAO_PCT and o["comissao"] >= KIT_COMISSAO_RS
            and not o.get("internacional")
            and not any(p in nome for p in config.PALAVRAS_PROIBIDAS)
            and not variedade.franquia(o) and not _postado_recente(fila, o["id"]))


def _pontos(o):
    return min(o["vendas"], 10000) / 1000 + (o["nota"] - 4.7) * 20 + o["comissao_pct"] / 2 + min(o["comissao"], 20) / 2


def melhor_do_termo(termo, teto, fila, ja, tema_titulo=""):
    """O melhor produto que é mesmo o buscado. `ja` = itens já no kit (para não repetir produto nem família)."""
    from . import busca_ze, shopee, variedade
    nos = []
    for pagina, ordem in ((1, 1), (2, 1), (1, 2)):
        for tentativa in (1, 2):   # a Shopee às vezes devolve "System Error" e responde na segunda
            try:
                nos += shopee.buscar_ofertas(termo, pagina, 50, ordem)
                break
            except Exception as e:
                print(f"⚠️  Shopee '{termo}' (página {pagina}, ordem {ordem}, tentativa {tentativa}): {e}")
                time.sleep(3)
    vistos, bons = set(), []
    familias = {variedade.familia(x) for x in ja}
    for n in nos:
        o = normalizar(n, "kit", termo)
        if o["id"] in vistos:
            continue
        vistos.add(o["id"])
        if (busca_ze.relevante(o["nome"], termo) and _passa(o, teto, fila)
                and variedade.familia(o) not in familias
                and not any(busca_ze._mesmo_produto(o, x) for x in ja)):
            bons.append(o)
    bons = sorted(bons, key=_pontos, reverse=True)[:12]
    conferidos = _filtro_ia(tema_titulo, termo, bons)
    if conferidos is not None:
        bons = conferidos
    return bons[0] if bons else None


PROMPT_IA = """Estou montando um post "{tema}" com achados da Shopee. Para o item "{termo}", encontrei
os produtos abaixo (número: nome). Quais SÃO de fato um(a) "{termo}" e combinam com o tema "{tema}"?
Não conta acessório, peça, refil, nem produto de outro tipo que só cita a palavra (ex.: buscando "organizador de
banheiro", sapateira ou organizador de armário NÃO servem).
Para cada um que servir, escreva um título curto em português, de 2 a 5 palavras, sem marca, sem medidas e sem
palavras de anúncio (ex.: "Dispenser de sabonete automático").
Responda só com JSON {{"ok": [{{"n": número, "titulo": "..."}}]}}, do mais adequado para o menos.

{lista}"""


def _filtro_ia(tema, termo, ofs):
    """A IA confere se cada produto é o item buscado e combina com o tema, e dá um título curto. None = IA fora."""
    if not config.GROQ_API_KEY or not ofs:
        return None
    from .legenda import _chamar_groq
    lista = "\n".join(f"{i}: {o['nome'][:110]}" for i, o in enumerate(ofs))
    try:
        bruto = _chamar_groq(PROMPT_IA.format(tema=tema.title(), termo=termo, lista=lista))
        ok = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0)).get("ok", [])
        saida = []
        for x in ok:
            n = x.get("n") if isinstance(x, dict) else x
            if str(n).isdigit() and int(n) < len(ofs):
                o = ofs[int(n)]
                t = str(x.get("titulo", "")).strip() if isinstance(x, dict) else ""
                if 3 <= len(t) <= 42:
                    o["titulo_ia"] = t[:1].upper() + t[1:]
                saida.append(o)
        return saida
    except Exception as e:
        print(f"⚠️  IA não conferiu '{termo}' ({e}); fico só com as regras.")
        return None


def _titulo(nome, n=42):
    t = re.sub(r"[\[\(【].*?[\]\)】]", " ", nome)
    t = re.sub(r"(?i)\b(envio imediato|pronta entrega|promo[cç][aã]o|frete gr[aá]tis|original|lan[cç]amento)\b", " ", t)
    t = " ".join(t.replace("|", " ").replace("/", " / ").split()).strip(" -–,.+")
    if len(t) > n:
        t = t[:n].rsplit(" ", 1)[0].rstrip(" -–,.+/")
    soltas = {"para", "pra", "de", "do", "da", "dos", "das", "com", "sem", "e", "a", "o", "em", "no", "na", "prova", "anti"}
    while " " in t and t.rsplit(" ", 1)[1].lower() in soltas:
        t = t.rsplit(" ", 1)[0]
    return t[:1].upper() + t[1:]


def escolher(tema, conferir_foto=True):
    cfg = TEMAS[tema]
    fila = carregar_fila()
    itens = []
    for termo in cfg["termos"]:
        if len(itens) >= QTD:
            break
        o = melhor_do_termo(termo, cfg["teto"], fila, [it["oferta"] for it in itens], cfg["titulo"])
        if not o:
            print(f"   '{termo}': nada que passe nas regras.")
            continue
        o["titulo"] = o.pop("titulo_ia", None) or _titulo(o["nome"])
        cabeca = " ".join(o["titulo"].lower().split()[:2])
        if any(" ".join(it["oferta"]["titulo"].lower().split()[:2]) == cabeca for it in itens):
            print(f"   '{termo}': {o['titulo']} repete um item do kit; pulando.")
            continue
        try:
            foto = imagem._baixar_foto(o["imagem"]) if conferir_foto else None
        except Exception as e:
            print(f"⚠️  Foto de {o['id']} não baixou ({e}).")
            continue
        itens.append({"oferta": o, "foto": foto, "termo": termo})
        print(f"🧺 {len(itens)}. '{termo}' → {o['nome'][:60]} — R$ {o['preco_fmt']} "
              f"(nota {o['nota']}, {o['vendas']} vendas, {o['comissao_pct']}%/R$ {o['comissao']})")
    return itens


# ---------------------------------------------------------------- artes
def capa(tema, itens):
    """Capa: o tema bem grande e as fotos dos 4 primeiros num quadro 2x2 (é o que aparece no feed e na grade)."""
    cfg = TEMAS[tema]
    maior = max(it["oferta"]["preco"] for it in itens)
    img = Image.new("RGB", (L, A))
    d = ImageDraw.Draw(img)
    for y in range(A):
        k = y / A
        d.line([(0, y), (L, y)], fill=(int(70 - 34 * k), int(40 - 20 * k), int(14 - 7 * k)))
    # etiqueta
    fe = imagem._fonte(34, "ExtraBold")
    t = "KIT DO ZÉ"
    w = d.textlength(t, font=fe) + 60
    d.rounded_rectangle(((L - w) / 2, 50, (L + w) / 2, 106), 28, fill=imagem.DOURADO)
    d.text((L / 2, 79), t, font=fe, fill=imagem.ESCURO, anchor="mm")
    # título (até 2 linhas)
    ft = imagem._fonte(96, "Black")
    linhas = imagem._quebrar(d, cfg["titulo"], ft, L - 120, max_linhas=2)
    y = 130
    for ln in linhas:
        d.text((L / 2, y), ln, font=ft, fill=imagem.DOURADO_CLARO, anchor="ma")
        y += ft.size + 10
    sub = f"{len(itens)} achados até R$ {int(round(maior + 0.49))}"
    d.text((L / 2, y + 6), sub, font=imagem._fonte(46, "SemiBold"), fill=imagem.BRANCO, anchor="ma")
    # quadro 2x2
    topo = y + 90
    base = A - 150
    lado = min((L - 60 * 2 - 30) // 2, (base - topo - 30) // 2)
    x0 = (L - (lado * 2 + 30)) // 2
    for i, it in enumerate(itens[:4]):
        cx = x0 + (i % 2) * (lado + 30)
        cy = topo + (i // 2) * (lado + 30)
        d.rounded_rectangle((cx, cy, cx + lado, cy + lado), 34, fill=imagem.BRANCO)
        if it.get("foto") is not None:
            fo = ImageOps.contain(it["foto"].convert("RGB"), (lado - 40, lado - 40), Image.LANCZOS)
            img.paste(fo, (cx + (lado - fo.width) // 2, cy + (lado - fo.height) // 2))
        r = 40
        d.ellipse((cx + 14, cy + 14, cx + 14 + 2 * r, cy + 14 + 2 * r), fill=imagem.ESCURO,
                  outline=imagem.DOURADO, width=4)
        d.text((cx + 14 + r, cy + 16 + r), str(i + 1), font=imagem._fonte(50, "Black"), fill=imagem.DOURADO_CLARO,
               anchor="mm")
    # rodapé
    d.rectangle([0, A - 118, L, A], fill=imagem.ESCURO)
    fr = imagem._fonte(40, "ExtraBold")
    partes = [("SALVA ", imagem.DOURADO_CLARO), ("PRA NÃO ESQUECER  •  ARRASTA ", imagem.BRANCO), ("→", imagem.DOURADO_CLARO)]
    x = (L - sum(d.textlength(t, font=fr) for t, _ in partes)) / 2
    for t, cor in partes:
        d.text((x, A - 82), t, font=fr, fill=cor)
        x += d.textlength(t, font=fr)
    return img


def legenda(tema, itens):
    from .ze import dias_para_black_friday
    cfg = TEMAS[tema]
    maior = int(round(max(it["oferta"]["preco"] for it in itens) + 0.49))
    linhas = [f"🧺 {cfg['gancho'].format(teto=maior, n=len(itens))}", ""]
    for i, it in enumerate(itens):
        o = it["oferta"]
        linhas.append(f"{NUM[i]} {o['titulo']} — R$ {o['preco_fmt']}")
    linhas += ["", "📌 Salva pra não esquecer e manda pra quem tá precisando!",
               "👇 Comenta QUERO + o número (ex.: QUERO 2) que o Zé te manda o link no direct.",
               "🔎 Faltou alguma coisa? Comenta o que você procura que o Zé garimpa pra você 🤠"]
    dias = dias_para_black_friday()
    if 0 < dias <= 45:
        linhas.append(f"⏳ Faltam {dias} dias pra Black Friday! Segue o Zé pra ver tudo primeiro.")
    linhas += ["", "Preços conferidos na hora do post, podem mudar na loja. Links de afiliado: você paga o mesmo.",
               "", f"{cfg['hashtags']} #zegarimpo #achadinhosshopee"]
    return "\n".join(linhas)


# linha de "manda pra alguém" no slide final, pelo tema (30/10/2026)
COMPARTILHA = {"banheiro": "Conhece alguém arrumando o banheiro? Manda esse kit pra essa pessoa",
               "cozinha": "Conhece alguém que vive na cozinha? Manda esse kit pra essa pessoa",
               "amigo-secreto": "Manda esse kit no grupo do amigo secreto",
               "natal": "Conhece alguém que ainda não comprou os presentes? Manda pra essa pessoa",
               "festa": "Vai ter festa? Manda esse kit pra quem vai organizar",
               "pet": "Conhece alguém que tem pet em casa? Manda esse kit pra essa pessoa",
               "carro": "Conhece alguém que vive dentro do carro? Manda esse kit pra essa pessoa",
               "home-office": "Conhece alguém que trabalha em casa? Manda esse kit pra essa pessoa"}


def gerar(tema, itens, pasta):
    from .achados import slide_final, slide_produto, slides_tiktok
    for it in itens:   # número fixo do achado (#142): TikTok, YouTube e busca da página da bio
        numeros.numerar(it["oferta"])
    pasta.mkdir(parents=True, exist_ok=True)
    marca = int(time.time())
    v = len(_carregar_estado()["temas"])
    arqs = []
    nome = f"kit-{tema}-{marca}-1.jpg"
    capa(tema, itens).save(pasta / nome, quality=92)
    arqs.append(nome)
    for i, it in enumerate(itens, 1):
        nome = f"kit-{tema}-{marca}-{i + 1}.jpg"
        slide_produto(it["oferta"], it["foto"], i, pasta / nome, v)
        arqs.append(nome)
    nome = f"kit-{tema}-{marca}-{len(itens) + 2}.jpg"
    slide_final(len(itens), v, COMPARTILHA.get(tema)).save(pasta / nome, quality=92)
    arqs.append(nome)
    tiktok = slides_tiktok(itens, pasta, f"kit-{tema}-{marca}", v, arqs[0])
    return {"tema": tema, "titulo": TEMAS[tema]["titulo"], "arquivos": arqs, "legenda": legenda(tema, itens),
            "tiktok": tiktok, "legenda_tiktok": tiktok_kit.legenda([it["oferta"] for it in itens], TEMAS[tema]["titulo"])
            if tiktok else "",
            "itens": [{k: it["oferta"].get(k) for k in ("id", "nome", "titulo", "preco_fmt", "preco", "link_afiliado",
                                                         "plataforma", "imagem", "nota", "vendas", "comissao",
                                                         "comissao_pct", "loja", "categoria", "palavra", "num")}
                      for it in itens]}


# ---------------------------------------------------------------- preparar / publicar
def preparar(tema=None):
    _saida("tem_post", "false")
    if not instagram.tem_token():
        print("⏸️  Token do Instagram ausente — kit em espera.")
        return
    # se o tema da vez não fechar o kit, tenta os próximos (até 3 temas)
    primeiro = tema if tema in TEMAS else tema_da_vez()
    usados = _carregar_estado()["temas"]
    outros = sorted((t for t in TEMAS if t != primeiro and (not TEMAS[t]["meses"] or agora().month in TEMAS[t]["meses"])),
                    key=lambda t: usados.get(t, ""))
    for tema in [primeiro] + outros[:2]:
        print(f"🧺 Kit da vez: {TEMAS[tema]['titulo']}")
        itens = escolher(tema)
        if len(itens) >= MINIMO:
            break
        print(f"⚠️  Só {len(itens)} produtos bons para o kit {tema} — tentando outro tema.")
    else:
        print("⚠️  Nenhum kit fechou hoje — sai o carrossel normal no lugar.")
        return
    pasta = PASTA_SITE / "midia" / "kits"
    (PASTA_SITE / ".nojekyll").parent.mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    for fixo in (config.RAIZ / "assets" / "paginas").glob("*.[ht][tx][mt]*"):
        (PASTA_SITE / fixo.name).write_text(fixo.read_text(encoding="utf-8"), encoding="utf-8")
    info = gerar(tema, itens, pasta)
    ARQ_PROXIMO.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    _saida("tem_post", "true")
    print(f"🧺 Kit {tema} preparado com {len(itens)} produtos.")


def publicar():
    from .achados import espelhar
    from .postar import _esperar_url
    info = json.loads(ARQ_PROXIMO.read_text(encoding="utf-8"))
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PAGES_URL ausente.")
    urls = [f"{base}/midia/kits/{a}" for a in info["arquivos"]]
    for u in urls:
        _esperar_url(u)
    ig_id = instagram.conferir_conta()["user_id"]
    filhos = [instagram.criar_item_carrossel(ig_id, imagem_url=u) for u in urls]
    for c in filhos:
        instagram.aguardar_container(c)
    cont = instagram.criar_carrossel(ig_id, filhos, info["legenda"])
    instagram.aguardar_container(cont)
    media_id = instagram.publicar(ig_id, cont)
    permalink = instagram.permalink(media_id)
    agora_s = agora().strftime(FMT)
    # registro que o responder lê ("QUERO 2" → link do 2º; só "QUERO" → lista com todos)
    dados = json.loads(ARQ_TOP.read_text(encoding="utf-8")) if ARQ_TOP.exists() else {"posts": {}}
    dados["posts"][media_id] = {"tipo": "kit", "rotulo": agora().strftime("%d/%m"), "titulo": f"kit {info['titulo'].title()}",
                                "itens": info["itens"], "postado_em": agora_s, "permalink": permalink}
    limite = (agora() - timedelta(days=60)).strftime(FMT)
    dados["posts"] = {k: v for k, v in dados["posts"].items() if v.get("postado_em", "") >= limite}
    ARQ_TOP.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    # entram na fila como postados: assim não se repetem por 30 dias no Instagram
    fila = carregar_fila()
    for it in info["itens"]:
        reg = fila["ofertas"].setdefault(it["id"], dict(it, criado_em=agora_s))
        reg.update({"status": "postado", "formato": "kit", "postado_em": agora_s, "postado_ts": time.time(),
                    "achados_post": media_id, "permalink": permalink})
        if it.get("num"):
            reg["num"] = it["num"]
    salvar_fila(fila)
    if not ANA:   # os achados do kit entram na página da bio (e na busca pelo número)
        from . import vitrine
        vitrine.gerar()
    if not ANA:
        extras = espelhar(dict(info, short=None), urls, base)
        if extras:
            dados["posts"][media_id].update(extras)
            ARQ_TOP.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    estado = _carregar_estado()
    estado["temas"][info["tema"]] = agora_s
    ARQ_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    if info.get("tiktok"):
        tiktok_kit.enviar([PASTA_SITE / "midia" / "kits" / x for x in info["tiktok"]], info["legenda_tiktok"])
    ARQ_PROXIMO.unlink(missing_ok=True)
    print(f"✅ Kit {info['tema']} publicado ({config.ARROBA}): {permalink or media_id}")


def previa(tema=None):
    temas = list(TEMAS) if tema == "todos" else [tema if tema in TEMAS else tema_da_vez()]
    raiz = config.RAIZ / "data" / "relatorios" / "kits"
    shutil.rmtree(raiz, ignore_errors=True)
    resumo = []
    for t in temas:
        print(f"\n===== {TEMAS[t]['titulo']} =====")
        itens = escolher(t)
        resumo.append(f"{t}: {len(itens)} produtos")
        if len(itens) < MINIMO:
            print(f"⚠️  Só {len(itens)} produtos — esse kit não sairia.")
            continue
        pasta = raiz / t
        info = gerar(t, itens, pasta)
        (pasta / "legenda.txt").write_text(info["legenda"], encoding="utf-8")
        print(info["legenda"])
    (raiz).mkdir(parents=True, exist_ok=True)
    (raiz / "resumo.txt").write_text("\n".join(resumo) + "\n", encoding="utf-8")
    print("\n" + "\n".join(resumo))


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    funcs = {"preparar": lambda: preparar(arg), "publicar": publicar, "previa": lambda: previa(arg)}
    if acao not in funcs:
        print("Uso: python -m src.kits preparar [tema] | publicar | previa [tema|todos]")
        sys.exit(2)
    try:
        funcs[acao]()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
