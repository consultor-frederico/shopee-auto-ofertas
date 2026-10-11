"""🤔 "Zé, isso vale a pena?" — a pessoa manda no direct o link (ou o print) de um produto da Shopee
e o Zé responde se vale a pena, com dados reais: nota, vendas e preço comparado com os parecidos
(src/raio_x.py). Se achar uma opção melhor ou mais barata, manda junto com o link de afiliado.

Ligado no direct pelo src/busca_ze.rodar_dms (mensagem com link da Shopee ou com imagem).

Teste: python -m src.vale_a_pena "https://shopee.com.br/...-i.123.456"
       python -m src.vale_a_pena visao-teste      (gera um print de mentira e lê com a IA)
"""
import base64
import json
import os
import re
from urllib.parse import unquote

import requests

from . import config
from .raio_x import brl, comparar

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}
RE_LINK = re.compile(r"https?://[^\s<>\"']*(?:shopee\.com\.br|shope\.ee|s\.shopee\.com\.br)[^\s<>\"']*", re.I)
RE_IDS = [re.compile(r"-i\.(\d+)\.(\d+)"),                    # nome-do-produto-i.LOJA.ITEM
          re.compile(r"/product/(\d+)/(\d+)"),                 # /product/LOJA/ITEM
          re.compile(r"shopee\.com\.br/[^/?#]+/(\d{3,})/(\d{6,})")]   # /loja/LOJA/ITEM
MODELOS_VISAO = [m.strip() for m in os.getenv(
    "GROQ_MODELOS_VISAO", "meta-llama/llama-4-scout-17b-16e-instruct,meta-llama/llama-4-maverick-17b-128e-instruct"
).split(",") if m.strip()]

PROMPT_VISAO = """Esta imagem é um print de um produto de loja online (provavelmente Shopee).
Responda só com JSON: {"loja_online": true/false, "nome": "nome do produto como aparece", "preco": número ou null}
"preco" é o preço atual (o menor, se tiver de/por), só o número com ponto decimal (ex.: 59.9).
Se a imagem não for um produto de loja, responda {"loja_online": false, "nome": "", "preco": null}."""


# ------------------------------------------------------------------ achar o produto
def tem_link(texto):
    return bool(RE_LINK.search(texto or ""))


def _ids(url):
    url = unquote(unquote(url))
    for rx in RE_IDS:
        m = rx.search(url)
        if m:
            return int(m.group(1)), int(m.group(2))
    m_item, m_loja = re.search(r"itemid=(\d+)", url, re.I), re.search(r"shopid=(\d+)", url, re.I)
    if m_item:
        return (int(m_loja.group(1)) if m_loja else None), int(m_item.group(1))
    return None


def _nome_do_link(url):
    m = re.search(r"shopee\.com\.br/([^/?#]+)-i\.\d+\.\d+", unquote(url))
    return m.group(1).replace("-", " ").strip() if m else ""


def _resolver(url):
    """Link curto (s.shopee.com.br, shope.ee) → link completo do produto."""
    if _ids(url):
        return url
    try:
        r = requests.get(url, headers=UA, timeout=20, allow_redirects=True)
        candidatos = [h.url for h in r.history] + [r.url]
        candidatos += re.findall(r"https?://shopee\.com\.br/[^\s\"'<>]+", r.text[:20000])
        for c in candidatos:
            if _ids(c):
                return c
        return r.url
    except Exception as e:
        print(f"⚠️  Vale a pena: não abri o link curto ({e}).")
        return url


def produto_do_link(texto):
    """Devolve o produto (dados da API de afiliados) ou um parcial {"nome"} ou None."""
    from . import shopee
    from .garimpar import normalizar
    m = RE_LINK.search(texto or "")
    if not m:
        return None
    url = _resolver(m.group(0).rstrip(".,;!)"))
    ids = _ids(url)
    if ids:
        try:
            nos = shopee.buscar_por_item(ids[1])
            if nos:
                return normalizar(nos[0], "vale_a_pena", "")
        except Exception as e:
            print(f"⚠️  Vale a pena: API não trouxe o item {ids[1]} ({e}).")
    nome = _nome_do_link(url)
    return {"nome": nome, "parcial": True} if nome else {"parcial": True, "nome": ""}


_visao_ok = []


def _modelos_visao(headers):
    """Modelos que enxergam imagem: os da config + os que a Groq listar com cara de visão."""
    if _visao_ok:
        return list(_visao_ok)
    lista = list(MODELOS_VISAO)
    try:
        r = requests.get(f"{config.GROQ_URL}/models", headers=headers, timeout=20)
        ids = [m["id"] for m in r.json().get("data", [])]
        print(f"ℹ️  Modelos da Groq: {ids}")
        lista += [i for i in ids if re.search(r"vision|llama-4|scout|maverick|[-_/]vl|gemma-3|pixtral|kimi|qwen3\.[5-9]", i, re.I)]
    except Exception as e:
        print(f"⚠️  Não listei os modelos da Groq ({e}).")
    return list(dict.fromkeys(lista))


def _visao(imagem_bytes):
    """Lê nome e preço de um print com um modelo de visão da Groq."""
    if not config.GROQ_API_KEY:
        return None
    dados = "data:image/jpeg;base64," + base64.b64encode(imagem_bytes).decode()
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"}
    for modelo in _modelos_visao(headers):
        try:
            r = requests.post(f"{config.GROQ_URL}/chat/completions", headers=headers, timeout=60, json={
                "model": modelo, "temperature": 0.1, "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": PROMPT_VISAO},
                    {"type": "image_url", "image_url": {"url": dados}}]}]})
            if r.status_code != 200:
                print(f"⚠️  Visão/{modelo}: HTTP {r.status_code} {r.text[:150]}")
                continue
            bruto = r.json()["choices"][0]["message"]["content"]
            if modelo not in _visao_ok:
                _visao_ok.insert(0, modelo)
            return json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
        except Exception as e:
            print(f"⚠️  Visão/{modelo}: {e}")
    return None


def _jpeg(imagem_bytes):
    """Reduz o print (a Groq aceita até ~4 MB em base64)."""
    from io import BytesIO
    from PIL import Image
    im = Image.open(BytesIO(imagem_bytes)).convert("RGB")
    im.thumbnail((1280, 1280))
    buf = BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def produto_do_print(url_imagem):
    from .busca_ze import relevante
    try:
        r = requests.get(url_imagem, headers=UA, timeout=30)
        r.raise_for_status()
        lido = _visao(_jpeg(r.content))
    except Exception as e:
        print(f"⚠️  Vale a pena: não li o print ({e}).")
        return None
    if not lido or not lido.get("loja_online") or not (lido.get("nome") or "").strip():
        return None
    nome = lido["nome"].strip()
    try:
        preco = float(str(lido.get("preco") or 0).replace(",", "."))
    except ValueError:
        preco = 0.0
    # tenta achar o próprio produto na Shopee pelo nome (mesmo tipo e preço parecido)
    from .raio_x import _buscar, termo
    t = termo(nome)
    for o in _buscar(nome[:80])[:20]:
        if relevante(o["nome"], t) and (not preco or abs(o["preco"] / preco - 1) <= 0.12):
            o["do_print"] = True
            return o
    return {"nome": nome, "preco": preco, "parcial": True, "do_print": True} if preco else {"nome": nome, "parcial": True}


# ------------------------------------------------------------------ analisar
def _boa(o):
    return o["nota"] >= 4.6 and o["vendas"] >= 100 and o.get("link_afiliado")


def _pontos(o):
    return (o["nota"] >= 4.8, min(o["vendas"], 5000) * o["nota"])


def analisar(prod):
    """Veredito com os motivos e até 2 opções melhores."""
    r = comparar(prod, mesmo_tipo=True)
    preco, nota, vendas = prod.get("preco") or 0, prod.get("nota"), prod.get("vendas")
    pros, contras = [], []
    if nota is not None and not prod.get("parcial"):
        if nota >= 4.7:
            pros.append(f"nota alta ({nota:.1f})".replace(".", ","))
        elif nota < 4.5:
            contras.append(f"nota baixa ({nota:.1f})".replace(".", ","))
    if vendas is not None and not prod.get("parcial"):
        if vendas >= 500:
            pros.append(f"muita gente já comprou ({vendas:,}+)".replace(",", "."))
        elif vendas < 30:
            contras.append("pouquíssimas vendas ainda, então é arriscado")
    pct = r["pct"]
    if pct is not None:
        if pct <= -10:
            pros.append(f"preço {-pct}% abaixo da média de {r['n']} parecidos")
        elif pct >= 20:
            contras.append(f"preço {pct}% acima da média de {r['n']} parecidos (R$ {brl(r['mediana'])})")
    opcoes = []
    if preco:
        for o in sorted((o for o in r["parecidos"] if _boa(o)), key=_pontos, reverse=True):
            mais_barata = o["preco"] <= preco * 0.9 and o["nota"] >= (nota or 0) - 0.1
            melhor = (o["preco"] <= preco * 1.05 and o["nota"] >= (nota or 0) + 0.2
                      and o["vendas"] > (vendas or 0))
            if mais_barata or melhor:
                o["motivo"] = "mais barata" if mais_barata else "mais bem avaliada"
                opcoes.append(o)
            if len(opcoes) == 2:
                break
    if any("nota baixa" in c or "arriscado" in c for c in contras):
        veredito = "⚠️ Eu teria cuidado com esse."
    elif contras or (opcoes and len(pros) < 2):
        veredito = "🤔 Dá pra achar melhor."
    elif pros:
        veredito = "✅ Vale a pena!"
    else:
        veredito = "🤷 Não tenho dados suficientes para cravar."
    return {"veredito": veredito, "pros": pros, "contras": contras, "opcoes": opcoes, "raio_x": r}


def _curto(nome, n=45):
    from .busca_ze import _curto as c
    return c(nome, n)


def mensagem(prod, a):
    linhas = ["Oi! 🤠 Aqui é o Zé Garimpo. Dei uma garimpada nesse produto:", ""]
    if prod.get("nome"):
        linhas.append(f"📦 {_curto(prod['nome'], 60)}")
    dados = []
    if not prod.get("parcial"):
        dados.append(f"⭐ {prod['nota']:.1f}".replace(".", ","))
        dados.append(f"{prod['vendas']:,}+ vendidos".replace(",", "."))
    if prod.get("preco"):
        dados.append(f"R$ {brl(prod['preco'])}")
    if dados:
        linhas.append(" · ".join(dados))
    linhas += ["", f"Veredito: {a['veredito']}"]
    linhas += [f"👍 {p}" for p in a["pros"]] + [f"👎 {c}" for c in a["contras"]]
    if a["opcoes"]:
        linhas += ["", "💡 Se quiser economizar, achei estas:" if a["veredito"].startswith("✅")
                   else "💡 Achei opção melhor:"]
        for i, o in enumerate(a["opcoes"], 1):
            nota = f"{o['nota']:.1f}".replace(".", ",")
            linhas.append(f"{i}️⃣ {_curto(o['nome'], 40)}: R$ {o['preco_fmt']} (⭐ {nota}, {o['motivo']})")
    linhas += ["", "Dica: antes de comprar, olha as fotos das avaliações 😉"]
    if prod.get("link_afiliado") or a["opcoes"]:
        linhas.append(f"(links de afiliado: você paga o mesmo e ajuda o {config.NOME_MARCA})")
    return "\n".join(linhas)


def botoes(prod, a):
    b = []
    if prod.get("link_afiliado"):
        b.append({"type": "web_url", "url": prod["link_afiliado"], "title": "🛒 Ver esse produto"})
    for i, o in enumerate(a["opcoes"], 1):
        b.append({"type": "web_url", "url": o["link_afiliado"], "title": f"💡 Ver opção {i}"})
    return b[:3]


NAO_ACHEI = ("Oi! 🤠 Aqui é o Zé Garimpo. Não consegui abrir esse produto 😅 "
             "Me manda o link completo da Shopee (no app: Compartilhar → Copiar link) "
             "ou um print que mostre o nome e o preço, que eu te digo se vale a pena!")


def responder(api, ig_id, autor, texto="", url_imagem=None):
    """Analisa e responde no direct. Devolve (resposta da API, status)."""
    enviar = lambda msg: api._req("POST", f"{ig_id}/messages", json={"recipient": {"id": autor}, "message": msg})
    prod = produto_do_link(texto) if tem_link(texto) else None
    if (not prod or not prod.get("nome")) and url_imagem:
        prod = produto_do_print(url_imagem) or prod
    if not prod and not tem_link(texto):
        return None, "ignorado"          # foto que não é de produto (meme, selfie...): não se mete
    if not prod or not prod.get("nome"):
        return enviar({"text": NAO_ACHEI}), "nao_achou"
    if prod.get("parcial") and not prod.get("preco"):
        # sem preço não dá para comparar: manda os melhores do mesmo tipo
        from . import busca_ze
        from .raio_x import termo
        t = termo(prod["nome"])
        ofs = busca_ze.achados(t) if t else []
        if not ofs:
            return enviar({"text": NAO_ACHEI}), "nao_achou"
        return busca_ze.enviar_dm(api, ig_id, None, t, ofs, destinatario=autor), "parecidos"
    a = analisar(prod)
    txt, bts = mensagem(prod, a), botoes(prod, a)
    if bts:
        try:
            return enviar({"attachment": {"type": "template", "payload": {
                "template_type": "button", "text": txt[:640], "buttons": bts}}}), "analisado"
        except Exception as e:
            print(f"⚠️  Botões recusados ({e}); mandando os links no texto.")
            txt += "\n\n" + "\n".join(f"{x['title']}: {x['url']}" for x in bts)
    return enviar({"text": txt[:1000]}), "analisado"


if __name__ == "__main__":
    import sys
    args = sys.argv[1:] or ["https://shopee.com.br/product/335317330/21199078523"]
    for arg in args:
        print(f"\n🤔 {arg}")
        if arg == "visao-teste":
            from io import BytesIO
            from PIL import Image, ImageDraw, ImageFont
            im = Image.new("RGB", (720, 900), "white")
            d = ImageDraw.Draw(im)
            f = ImageFont.truetype(str(config.FONTE), 34)
            d.rectangle([40, 40, 680, 520], fill="#dddddd")
            d.text((40, 560), "Fone de Ouvido Bluetooth TWS\nSem Fio com Microfone", font=f, fill="black")
            d.text((40, 680), "R$ 39,90", font=ImageFont.truetype(str(config.FONTE), 52), fill="#ee4d2d")
            d.text((40, 760), "4.8 ★  |  5mil vendidos", font=f, fill="#555555")
            buf = BytesIO()
            im.save(buf, "JPEG")
            print("Leitura do print:", _visao(buf.getvalue()))
            continue
        prod = produto_do_link(arg) if tem_link(arg) else {"nome": arg, "parcial": True}
        print("Produto:", {k: prod.get(k) for k in ("id", "nome", "preco", "nota", "vendas", "parcial")} if prod else None)
        if prod and prod.get("preco"):
            print(mensagem(prod, analisar(prod)))
