"""Gera título curto (para a imagem) e legenda do Instagram com a Groq.
Se a IA falhar, usa um modelo de texto fixo — o post nunca sai com o nome cru da Shopee."""
import json
import re
import time

import requests

from . import config

_modelo_escolhido = None

_TAGS = {
    "eletronicos": "#achadinhos #shopee #ofertas #eletronicos #tecnologia #promoção",
    "lar": "#achadinhos #shopee #ofertas #casa #organização #utilidades",
    "brinquedos": "#achadinhos #shopee #ofertas #brinquedos #presente #criança",
    "feminino": "#achadinhos #shopee #ofertas #moda #beleza #achadinhosfemininos",
    "pet": "#achadinhos #shopee #ofertas #pet #cachorro #gato",
    "automotivo": "#achadinhos #shopee #ofertas #carro #automotivo #acessórios",
    "masculino": "#achadinhos #shopee #ofertas #modamasculina #estilo #homem",
    "manual": "#achadinhos #shopee #ofertas #achadosshopee #promoção",
    "beleza": "#achadinhos #shopee #beleza #maquiagem #skincare #achadinhosdebeleza",
    "cabelo": "#achadinhos #shopee #cabelo #cabelocacheado #cuidadoscomcabelo #beleza",
    "moda": "#achadinhos #shopee #moda #acessórios #lookdodia #estilo",
    "autocuidado": "#achadinhos #shopee #autocuidado #selfcare #bemestar #skincare",
    "casa_fofa": "#achadinhos #shopee #decoração #quartoaesthetic #casafofa #aesthetic",
}
EXTRA_PERFIL = {"ana": " #lgbtqia #orgulho"}
CTA = ("💚 Comenta QUERO que eu te mando o link no direct!" if config.PERFIL == "ana"
       else "👇 Comente EU QUERO que eu te envio o link no direct!")
HASHTAGS = {k: v + EXTRA_PERFIL.get(config.PERFIL, "") + " " + config.HASHTAG_MARCA for k, v in _TAGS.items()}

PROMPT = """Você é social media de uma página de achadinhos da Shopee chamada {marca}.
Público: {publico}. {tom}
Produto: {nome}
Preço: R$ {preco}{desconto}
Avaliação: {nota} estrelas, {vendas} vendidos.{achado}

Responda APENAS com um JSON válido, sem texto antes ou depois, no formato:
{{"titulo": "...", "legenda": "..."}}

Regras:
- "titulo": nome comercial curto do produto, no máximo 32 caracteres, sem emoji, sem marca de loja.
- "legenda": 3 a 5 linhas curtas separadas por \\n. Linha 1 é um gancho que desperta desejo.
  Depois, 1 ou 2 benefícios concretos. Mencione o preço uma vez. Use poucos emojis.
  NÃO invente características que não estão no nome do produto. NÃO coloque link nem hashtags.
  A última linha deve ser exatamente: {cta}"""


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
    return (f"{abre} {oferta['titulo']}\n"
            f"⭐ Nota {nota} e mais de {vendas} vendidos\n"
            f"💰 Por R$ {oferta['preco_fmt']}{desconto}\n"
            f"{CTA}")


def gerar(oferta: dict) -> dict:
    """Recebe a oferta normalizada e devolve {'titulo','legenda','fonte'}."""
    titulo = _titulo_padrao(oferta["nome"])
    base = {"titulo": titulo, "fonte": "modelo"}
    if not config.GROQ_API_KEY:
        print("⚠️  GROQ_API_KEY não configurada: usando legenda padrão.")
    else:
        desconto = f" ({oferta['desconto']}% OFF)" if oferta.get("desconto") else ""
        prompt = PROMPT.format(cta=CTA, marca=config.NOME_MARCA, publico=config.PUBLICO, tom=config.TOM,
                               nome=oferta["nome"], preco=oferta["preco_fmt"], desconto=desconto,
                               nota=oferta["nota"], vendas=oferta["vendas"],
                               achado=ACHADO if oferta.get("nivel") == "achado" else "")
        try:
            bruto = _chamar_groq(prompt)
            dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
            t = str(dados.get("titulo", "")).strip()[:40]
            leg = str(dados.get("legenda", "")).strip()
            if leg and "QUERO" in leg.upper():
                return {"titulo": t or titulo,
                        "legenda": leg + "\n\n" + HASHTAGS.get(oferta["categoria"], ""),
                        "fonte": "ia"}
            print("⚠️  Legenda da IA veio fora do padrão; usando legenda padrão.")
            if t:
                base["titulo"] = t
        except Exception as e:
            print(f"⚠️  Falha na legenda por IA ({e}); usando legenda padrão.")
    oferta_t = dict(oferta, titulo=base["titulo"])
    base["legenda"] = _legenda_padrao(oferta_t) + "\n\n" + HASHTAGS.get(oferta["categoria"], "")
    return base
