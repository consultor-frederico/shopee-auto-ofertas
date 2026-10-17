"""Gera título curto (para a imagem) e legenda do Instagram com a Groq.
Se a IA falhar, usa um modelo de texto fixo — o post nunca sai com o nome cru da Shopee."""
import json
import re
import time

import requests

from . import config

_modelo_escolhido = None

# Poucas hashtags e bem específicas (hoje elas só classificam o post; o que traz alcance é a
# palavra-chave na legenda e o post ser enviado/salvo). Regra das skills de Instagram: 3 a 5 tags
# "dimensionadas" (1 ampla + 1 da categoria + 1-2 do próprio produto + a da marca), nunca 30.
_TAGS = {
    "eletronicos": "#achadinhosshopee #gadgets #tecnologia #achadinhos",
    "lar": "#achadinhosshopee #casaorganizada #utilidadesdomesticas #achadinhos",
    "brinquedos": "#achadinhosshopee #brinquedos #presentecriativo #achadinhos",
    "feminino": "#achadinhosshopee #moda #beleza #achadinhos",
    "pet": "#achadinhosshopee #petlovers #cachorro #gato",
    "automotivo": "#achadinhosshopee #acessoriosautomotivos #carro #achadinhos",
    "masculino": "#achadinhosshopee #modamasculina #presenteparahomem #achadinhos",
    "manual": "#achadinhosshopee #achadinhos #promoção",
    "beleza": "#achadinhosshopee #beleza #skincare #achadinhos",
    "cabelo": "#achadinhosshopee #cabelo #cuidadoscomcabelo #achadinhos",
    "moda": "#achadinhosshopee #moda #lookdodia #achadinhos",
    "autocuidado": "#achadinhosshopee #autocuidado #selfcare #achadinhos",
    "casa_fofa": "#achadinhosshopee #decoração #quartoaesthetic #achadinhos",
}
EXTRA_PERFIL = {"ana": " #achadinhosfemininos #autocuidado"}
MAX_TAGS = 5
_TAGS_PROIBIDAS = {"#fyp", "#foryou", "#viral", "#explore", "#explorar", "#reels", "#instagood",
                   "#tbt", "#love", "#follow", "#seguir", "#like", "#curtir", "#sigoevolto"}
CTA = ("💚 Comenta QUERO que eu te mando o link no direct!" if config.PERFIL == "ana"
       else "👇 Comente EU QUERO que eu te envio o link no direct!")
HASHTAGS = {k: " ".join(dict.fromkeys((v + EXTRA_PERFIL.get(config.PERFIL, "") + " " + config.HASHTAG_MARCA).split()))
            for k, v in _TAGS.items()}   # sem hashtag repetida (ex.: #autocuidado da categoria e da Ana)


def _tag_ok(tag):
    t = tag.lower()
    if not re.fullmatch(r"#[a-z0-9_à-ÿ]{3,30}", t) or t in _TAGS_PROIBIDAS:
        return False
    if config.PERFIL == "ana" and ("garimp" in t or any(p in t for p in config._P.get("proibidas", []))):
        return False
    return True


def montar_hashtags(categoria, do_produto=(), plataforma=None):
    """No máximo 5: a ampla do perfil, a da categoria, até 2 do próprio produto (vindas da IA) e a da marca."""
    if plataforma == "sharkninja":   # marca oficial: troca as tags de "achadinhos da Shopee" pela da marca
        produto = [t if t.startswith("#") else "#" + t for t in (do_produto or [])]
        produto = [t for t in produto if _tag_ok(t)][:1]
        ampla = "#achadinhosfemininos" if config.PERFIL == "ana" else "#achadinhos"
        da_categoria = "#cabelo" if categoria == "cabelo" else "#casaorganizada"
        tags = list(dict.fromkeys(t.lower() for t in [ampla, da_categoria, "#sharkninja"] + produto))
        marca = [config.HASHTAG_MARCA] if config.HASHTAG_MARCA else []
        return " ".join(tags[:MAX_TAGS - len(marca)] + marca)
    base = (_TAGS.get(categoria) or _TAGS["manual"]).split()
    ampla = "#achadinhosfemininos" if config.PERFIL == "ana" else base[0]
    da_categoria = next((t for t in base[1:] if t not in ("#achadinhos", "#achadinhosshopee")), "#achadinhos")
    produto = [t if t.startswith("#") else "#" + t for t in (do_produto or [])]
    produto = [t for t in produto if _tag_ok(t)][:2]
    tags = list(dict.fromkeys(t.lower() for t in [ampla, da_categoria] + produto))
    tags += [t for t in base if t.lower() not in tags]          # completa se faltou tag do produto
    marca = [config.HASHTAG_MARCA] if config.HASHTAG_MARCA else []
    return " ".join(tags[:MAX_TAGS - len(marca)] + marca)


PROMPT = """Você é social media de uma página de achadinhos da Shopee chamada {marca}.
Público: {publico}. {tom}
Produto: {nome}
Preço: R$ {preco}{desconto}
Avaliação: {nota} estrelas, {vendas} vendidos.{achado}

Responda APENAS com um JSON válido, sem texto antes ou depois, no formato:
{{"titulo": "...", "legenda": "...", "hashtags": ["#...", "#..."]}}

Regras:
- "titulo": nome comercial curto do produto, no máximo 32 caracteres, sem emoji, sem marca de loja.
- "legenda": 3 a 5 linhas curtas separadas por \\n, com UMA ideia só.
  Linha 1 é o gancho e tem NO MÁXIMO 110 caracteres (o Instagram corta em ~125 com o "mais").
  Ela JÁ TRAZ O NOME do produto do jeito que as pessoas pesquisam no Instagram (ex.: "Porta tempero
  giratório: cozinha organizada em 1 minuto"), porque é isso que faz o post aparecer na busca.
  Depois, 1 ou 2 benefícios concretos. Prefira números a adjetivos: use a nota, as vendas e o preço
  (ex.: "nota 4,9 com mais de 2 mil vendidos" em vez de "super bem avaliado"). Mencione o preço uma vez.
  Use poucos emojis. NÃO invente características que não estão no nome do produto. NÃO coloque link nem hashtags.
  Escreva como gente, sem cara de texto de IA: no máximo 1 travessão (—) na legenda toda, nada de
  "imperdível", "incrível", "revolucionário", "eleve", "transforme", "descubra", "perfeito para você",
  "não perca", "você vai se surpreender".
  A página é uma curadoria de achadinhos: escolhe produtos pela nota e pelas vendas na Shopee, mas NÃO testa nem
  usa os produtos. Então NUNCA escreva como quem usou, testou, comprou ou tem o produto ("testei",
  "uso aqui em casa", "amei", "eu tenho", "recomendo") e NUNCA prometa resultado ("garantido",
  "dura muito", "não decepciona"). Fale do produto e do achado, não de experiência própria.{proibido}
  A última linha deve ser exatamente: {cta}
- "hashtags": 2 hashtags em português, minúsculas, sem acento, de nicho DESTE produto e de quem compra
  ele (ex.: boneca → "#brinquedoinfantil", "#presentedecrianca"; ring light → "#youtuber", "#criadordeconteudo").
  Nada genérico como #viral, #fyp, #explore, #ofertas ou #promoção."""

def _prompt_oficial():
    """Mesmo prompt, para produto de marca oficial (Shark Ninja): sem nota, vendas nem 'Shopee'."""
    trocas = [
        ("página de achadinhos da Shopee chamada", "página de achadinhos chamada"),
        ("Avaliação: {nota} estrelas, {vendas} vendidos.{achado}",
         "Marca: {marca_produto}, em loja oficial (programa de afiliados da marca).\n"
         "O que a marca diz do produto: {descricao}{achado}"),
        ("Prefira números a adjetivos: use a nota, as vendas e o preço\n"
         "  (ex.: \"nota 4,9 com mais de 2 mil vendidos\" em vez de \"super bem avaliado\"). Mencione o preço uma vez.",
         "Este produto NÃO tem nota nem vendas no feed: NUNCA cite nota, estrelas, avaliações ou vendidos.\n"
         "  Use o preço e só o que consta na descrição da marca. Mencione o preço uma vez."),
        ("escolhe produtos pela nota e pelas vendas na Shopee, mas NÃO testa nem",
         "separa ofertas de lojas oficiais, mas NÃO testa nem"),
        ("NÃO invente características que não estão no nome do produto.",
         "NÃO invente características que não estão no nome nem na descrição."),
    ]
    p = PROMPT
    for velho, novo in trocas:
        assert velho in p, f"prompt mudou: {velho[:40]}"   # se alguém mexer no PROMPT, o teste local avisa
        p = p.replace(velho, novo)
    return p


PROMPT_OFICIAL = _prompt_oficial()

# A Ana tem as palavras dela: "garimpo/garimpar" é do Zé (Garimpo VIP) e nunca aparece na Ana.
PROIBIDO_ANA = '\n  NUNCA use as palavras "garimpo", "garimpar", "garimpei" nem "garimpado".'


def _modelos_disponiveis(headers):
    try:
        r = requests.get(f"{config.GROQ_URL}/models", headers=headers, timeout=20)
        ids = [m["id"] for m in r.json().get("data", [])]
        return [i for i in ids if re.search(r"llama|gpt-oss|qwen|gemma|mistral", i, re.I)
                and not re.search(r"whisper|guard|tts|vision", i, re.I)]
    except Exception as e:
        print(f"⚠️  Não consegui listar modelos da Groq: {e}")
        return []


ACHADO = ("\nEste produto é um 💎 ACHADO ESCONDIDO: excelente avaliação, mas pouca gente conhece ainda. "
          "Use isso no gancho da linha 1 (ex.: \"Achado que quase ninguém conhece 💎\"), sem exagerar.")


_indisponiveis = set()   # modelos que a Groq disse não existir (não tenta de novo na mesma rodada)


def _espera_429(r):
    """Quantos segundos a Groq pediu para esperar (cabeçalho ou texto 'try again in 7.5s')."""
    try:
        return float(r.headers.get("retry-after"))
    except (TypeError, ValueError):
        m = re.search(r"try again in ([\d.]+)s", r.text)
        return float(m.group(1)) if m else 10.0


def _corpo(modelo, prompt):
    corpo = {"model": modelo, "temperature": 0.7,
             "messages": [{"role": "user", "content": prompt}],
             "response_format": {"type": "json_object"}}
    if "gpt-oss" in modelo:        # modelos que "pensam": pouco raciocínio, resposta direta
        corpo["reasoning_effort"] = "low"
    elif "qwen3" in modelo:
        corpo["reasoning_format"] = "hidden"
    return corpo


# Linha de "manda/salva": envio por DM e salvamento são os sinais que mais levam o post a quem não
# nos segue. Vai na penúltima linha (antes do "comente QUERO"), variando para não ficar repetitivo.
COMPARTILHA = {
    "pet": "📲 Manda pra quem tem pet em casa 🐾",
    "automotivo": "📲 Manda pra quem vive dentro do carro 🚗",
    "brinquedos": "📲 Manda pra quem tem criança em casa",
    "lar": "📲 Manda pra quem tá montando a casa 🏠",
    "eletronicos": "📲 Manda pra aquele amigo viciado em tecnologia",
    "masculino": "📲 Manda pro pai, parceiro ou amigo que ia curtir",
}
COMPARTILHA_GERAL = ["📲 Manda pra quem precisa ver isso!", "🔖 Salva pra não perder esse preço",
                     "📲 Envia pra quem ia amar isso", "🔖 Salva aqui e manda pra quem vai gostar"]


def linha_compartilhar(oferta):
    opcoes = COMPARTILHA_GERAL + ([COMPARTILHA[oferta["categoria"]]] * 2 if oferta.get("categoria") in COMPARTILHA else [])
    return opcoes[sum(map(ord, str(oferta.get("id", "")))) % len(opcoes)]


def com_compartilhar(legenda_txt, oferta):
    """Põe a linha de compartilhar logo antes da linha do QUERO."""
    linhas = legenda_txt.split("\n")
    i = next((k for k in range(len(linhas) - 1, -1, -1) if "QUERO" in linhas[k].upper()), len(linhas))
    return "\n".join(linhas[:i] + [linha_compartilhar(oferta)] + linhas[i:])


def _chamar_groq(prompt):
    global _modelo_escolhido
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"}
    candidatos = [m for m in ([_modelo_escolhido] if _modelo_escolhido else []) + list(config.GROQ_MODELOS)
                  if m not in _indisponiveis]
    candidatos = list(dict.fromkeys(candidatos))
    tentou_listar = False
    while candidatos:
        modelo = candidatos.pop(0)
        for tentativa in range(3):
            r = requests.post(f"{config.GROQ_URL}/chat/completions", headers=headers, timeout=60,
                              json=_corpo(modelo, prompt))
            if r.status_code == 200:
                _modelo_escolhido = modelo
                return r.json()["choices"][0]["message"]["content"]
            if r.status_code == 429 and tentativa < 2:     # limite por minuto: espera e tenta de novo
                espera = min(_espera_429(r) + 1, 30)
                print(f"⏳ Groq/{modelo}: limite por minuto — esperando {espera:.0f}s")
                time.sleep(espera)
                continue
            if r.status_code == 400 and "json_validate_failed" in r.text and tentativa < 1:
                continue                                    # resposta fora do JSON: tenta mais uma vez
            break
        print(f"⚠️  Groq/{modelo} respondeu HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code in (401, 403):
            raise RuntimeError("GROQ_API_KEY inválida ou sem permissão.")
        if r.status_code == 404:
            _indisponiveis.add(modelo)
            if _modelo_escolhido == modelo:
                _modelo_escolhido = None
        if not candidatos and not tentou_listar:
            tentou_listar = True
            candidatos = [m for m in _modelos_disponiveis(headers)
                          if m not in config.GROQ_MODELOS and m not in _indisponiveis]
            if candidatos:
                print(f"ℹ️  Tentando modelos disponíveis na Groq: {candidatos[:3]}")
                candidatos = candidatos[:3]
    raise RuntimeError("Nenhum modelo da Groq respondeu.")


def _titulo_padrao(nome):
    nome = re.sub(r"[\[\(].*?[\]\)]", "", nome)
    palavras, titulo = nome.split(), ""
    for p in palavras:
        if len(titulo) + len(p) + 1 > 32:
            break
        titulo = f"{titulo} {p}".strip()
    return titulo or nome[:32]


def _legenda_padrao(oferta):
    desconto = f" ({oferta['desconto']}% OFF)" if oferta.get("desconto") else ""
    nota = f"{oferta['nota']:.1f}".replace(".", ",")
    vendas = f"{oferta['vendas']:,}".replace(",", ".")
    abre = "✨ Achadinho que separei:" if config.PERFIL == "ana" else "🔥 Achadinho do dia:"
    if oferta.get("nivel") == "achado":
        abre = "💎 Achado escondido que pouca gente conhece:"
    prova = ("🏬 Loja oficial Shark Ninja" if oferta.get("plataforma") == "sharkninja"
             else f"⭐ Nota {nota} e mais de {vendas} vendidos")
    return (f"{abre} {oferta['titulo']}\n"
            f"{prova}\n"
            f"💰 Por R$ {oferta['preco_fmt']}{desconto}\n"
            f"{CTA}")


# A página só garimpa (não testa os produtos): legenda da IA que falar como quem usou é descartada,
# e promessa de resultado ("diversão garantida") sai do texto.
_USO = re.compile(r"\b(testei|testamos|testad[oa]s?|usei|usamos|uso (aqui|todo|em casa|sempre)|comprei|"
                  r"compramos|experimentei|amei|eu tenho|tenho (um|uma|o|a) |aqui em casa|lá em casa|"
                  r"recomendo|indico|garanto|aprovei|aprovamos)\b", re.I)
_PROMESSA = [
    (re.compile(r"\s*[–—-]\s*[\wÀ-ú ]{0,25}\bgarantid[oa]s?\b[!.]?", re.I), "."),
    (re.compile(r",?\s*[\wÀ-ú]+ garantid[oa]s?\b", re.I), ""),
    (re.compile(r",?\s*(e )?dura muito( tempo)?", re.I), ""),
    (re.compile(r",?\s*não decepciona", re.I), ""),
]


_CLICHE = {"imperdível", "incrível", "revolucionário", "revolucionária", "não perca", "simplesmente incrível"}


def sem_cara_de_ia(texto):
    """Mantém só o 1º travessão; os outros viram vírgula. Tira clichê solto ("— imperdível!")."""
    linhas = []
    visto = False
    for linha in texto.split("\n"):
        partes = [x for x in re.split(r"\s+[—–]\s+|\s*--\s*", linha)          # "— imperdível!" solto sai
                  if x.strip(" !.,") and x.strip(" !.,").lower() not in _CLICHE]
        nova = partes[0] if partes else ""
        for parte in partes[1:]:
            nova += (" — " if not visto else ", ") + parte
            visto = True
        linhas.append(re.sub(r"\s{2,}", " ", nova).strip().rstrip(",;—– "))
    return "\n".join(linhas)


def gancho_curto(texto, limite=125):
    """Se a 1ª linha passar do que aparece antes do "mais", corta na última palavra inteira."""
    linhas = texto.split("\n")
    if linhas and len(linhas[0]) > limite:
        corte = linhas[0][:limite].rsplit(" ", 1)[0].rstrip(" ,:;—-")
        linhas[0] = corte
    return "\n".join(linhas)


def sem_promessa(texto):
    for rx, troca in _PROMESSA:
        texto = rx.sub(troca, texto)
    return re.sub(r"\.\.+", ".", re.sub(r"[ \t]+([.,!])", r"\1", texto))


def fala_como_quem_usou(texto):
    return bool(_USO.search(texto or ""))


def gerar(oferta: dict) -> dict:
    """Recebe a oferta normalizada e devolve {'titulo','legenda','fonte'}."""
    titulo = _titulo_padrao(oferta["nome"])
    base = {"titulo": titulo, "fonte": "modelo"}
    if not config.GROQ_API_KEY:
        print("⚠️  GROQ_API_KEY não configurada: usando legenda padrão.")
    else:
        desconto = f" ({oferta['desconto']}% OFF)" if oferta.get("desconto") else ""
        modelo = PROMPT_OFICIAL if oferta.get("plataforma") == "sharkninja" else PROMPT
        prompt = modelo.format(cta=CTA, marca=config.NOME_MARCA, publico=config.PUBLICO, tom=config.TOM,
                               proibido=PROIBIDO_ANA if config.PERFIL == "ana" else "",
                               nome=oferta["nome"], preco=oferta["preco_fmt"], desconto=desconto,
                               nota=oferta["nota"], vendas=oferta["vendas"],
                               marca_produto=oferta.get("marca", ""), descricao=oferta.get("descricao", ""),
                               achado=ACHADO if oferta.get("nivel") == "achado" else "")
        try:
            bruto = _chamar_groq(prompt)
            dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
            t = str(dados.get("titulo", "")).strip()[:40]
            leg = str(dados.get("legenda", "")).strip()
            if leg and fala_como_quem_usou(leg):
                print("⚠️  Legenda da IA falou como quem usou o produto; usando legenda padrão.")
                leg = ""
            if leg and config.PERFIL == "ana" and re.search(r"garimp", leg, re.I):
                print("⚠️  Legenda da Ana veio com 'garimpo'; usando legenda padrão.")
                leg = ""
            leg = gancho_curto(sem_cara_de_ia(sem_promessa(leg)))
            tags_ia = dados.get("hashtags") if isinstance(dados.get("hashtags"), list) else []
            if leg and "QUERO" in leg.upper():
                return {"titulo": t or titulo,
                        "legenda": com_compartilhar(leg, oferta) + "\n\n"
                                   + montar_hashtags(oferta["categoria"], [str(x) for x in tags_ia],
                                                     oferta.get("plataforma")),
                        "fonte": "ia"}
            print("⚠️  Legenda da IA veio fora do padrão; usando legenda padrão.")
            if t:
                base["titulo"] = t
        except Exception as e:
            print(f"⚠️  Falha na legenda por IA ({e}); usando legenda padrão.")
    oferta_t = dict(oferta, titulo=base["titulo"])
    base["legenda"] = com_compartilhar(_legenda_padrao(oferta_t), oferta) + "\n\n" + montar_hashtags(oferta["categoria"], (), oferta.get("plataforma"))
    return base
