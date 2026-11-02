"""Curadoria: nota de "fator uau" pela IA e detecção de produtos repetidos/parecidos."""
import json
import re
import time
import unicodedata

from . import config, legenda

PROMPT_UAU = """Você é o curador MAIS EXIGENTE de uma página de achadinhos chamada {marca}
(público: {publico}). Os seguidores reclamam que só aparece produto comum (varal, pote,
vaporizador, liquidificador) e por isso não compram. Sua função é barrar o comum.

Para cada produto, responda duas coisas:
- "g" (gancho): em até 8 palavras, o motivo CONCRETO de alguém parar de rolar o feed para ver
  esse produto (ex.: "projeta o céu estrelado no teto do quarto", "corta legumes em espiral sem
  esforço"). Se o único motivo for "é útil", "é prático", "organiza", "é bonito" ou "bom preço",
  deixe "g" vazio.
- "n" (nota de 0 a 10 do fator uau): o quanto é DIFERENTE, curioso ou surpreendente.

Regras da nota:
- Gancho vazio = nota no máximo 5.
- 0-4: básico, reposição ou commodity — roupa básica, meia, cueca, tapete higiênico, papel,
  sacos, cabos, capinha comum, refil, peça de reposição, higiene comum, material escolar.
- 5 NO MÁXIMO: útil e bem vendido, mas COMUM, que se acha em qualquer loja ou supermercado
  (utilidade comum de casa nunca passa de 5, mesmo bem avaliada): varal,
  pote/porta-mantimento, organizador, cabide, prateleira, espelho, tapete, cortina, lixeira, cômoda,
  mesa de cabeceira, painel ripado, panela, liquidificador, batedeira, cafeteira, torradeira,
  ventilador, aquecedor, ferro/vaporizador de roupa, secador e chapinha comuns, aparelho de
  pressão, balança, travesseiro, almofada, luminária e fita LED comuns, umidificador comum,
  smartwatch, fone, power bank, carregador, caixa de som, ring light, aspirador, mochila, lanterna,
  brinquedo infantil comum (boneca, carrinho, blocos, pelúcia). Marca famosa NÃO sobe a nota:
  liquidificador de marca continua sendo liquidificador.
- 6-7: tem um detalhe esperto de verdade, mas a pessoa já viu parecido.
- 8: "não sabia que existia isso" — gadget curioso, solução criativa, efeito visual forte,
  presente que impressiona. A pessoa marcaria um amigo.
- 9-10: RARO, no máximo 1 em cada 15 — surpreendente e quase ninguém conhece.
- Nota 0: nome de franquia, marca famosa de personagem (filme, série, desenho, anime, time, grife)
  — risco de réplica; ou produto que não combina com o público acima (ex.: numa página para o
  público feminino, brinquedo infantil, ferramenta, isqueiro/acendedor, item automotivo ou masculino).
Na dúvida entre duas notas, escolha a MENOR.

Produtos (id, preço e nome):
{lista}

Responda APENAS com JSON no formato {{"notas": {{"<id>": {{"n": <nota>, "g": "<gancho ou vazio>"}}, ...}}}}
para todos os ids."""


def _norm(txt):
    txt = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode().lower()
    # marca escrita de jeitos diferentes conta igual: "DR.REJUALL" = "Dr.Reju-All" = "drrejuall"
    txt = re.sub(r"(?<=[a-z0-9])[.\-'’‑](?=[a-z0-9])", "", txt)
    return [t for t in re.findall(r"[a-z0-9]+", txt) if len(t) > 2]


PARADAS = {"com", "para", "kit", "unidades", "und", "pcs", "original", "promocao", "envio",
           "imediato", "novo", "nova", "pronta", "entrega", "atacado", "qualidade", "alta",
          "new", "official", "oficial", "loja", "store", "hot", "sale"}


def tokens(nome):
    return {t for t in _norm(nome) if t not in PARADAS}


def parecido(a, b, limite=0.55):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= limite


def _linha(o):
    preco = f'R$ {o["preco_fmt"]}' if o.get("preco_fmt") else ""
    return f'- id {o["id"]}: {preco} | {o["nome"][:110]}'


def notas_uau(ofertas, lote=40, ganchos=None):
    """Devolve {id: nota}. Sem IA disponível, devolve {} (quem chama decide o padrão).
    Se `ganchos` for um dict, ele recebe {id: motivo de parar de rolar} (vazio = produto comum)."""
    if not config.GROQ_API_KEY or not ofertas:
        return {}
    notas = {}
    for i in range(0, len(ofertas), lote):
        if i:
            time.sleep(6)   # respeita o limite de tokens por minuto do plano gratuito da Groq
        parte = ofertas[i:i + lote]
        lista = "\n".join(_linha(o) for o in parte)
        try:
            bruto = legenda._chamar_groq(PROMPT_UAU.format(marca=config.NOME_MARCA, publico=config.PUBLICO, lista=lista))
            dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
            for k, v in (dados.get("notas") or {}).items():
                gancho = ""
                if isinstance(v, dict):
                    gancho = str(v.get("g") or "").strip()
                    v = v.get("n")
                try:
                    nota = max(0.0, min(10.0, float(v)))
                except (TypeError, ValueError):
                    continue
                if len(gancho) < 8:
                    nota = min(nota, 5.0)   # sem motivo concreto para parar de rolar = produto comum
                notas[str(k)] = nota
                if ganchos is not None:
                    ganchos[str(k)] = gancho
        except Exception as e:
            print(f"⚠️  Curadoria por IA falhou neste lote ({e}).")
    return notas


# Critérios do Canal do WhatsApp (definidos pelo Fred em 22/10/2026): mais seletivo que o Instagram.
PROMPT_WHATSAPP = """Você é o curador do Canal do WhatsApp do Garimpo VIP.
Avalie cada produto com estes critérios:

1. ORIGINALIDADE: o produto deve apresentar uma ideia, função, formato ou utilização diferente do convencional.
2. DIFERENCIAÇÃO: deve ter algo especial que o distinga claramente dos produtos comuns.
3. EFEITO SURPRESA: deve despertar curiosidade, admiração, diversão ou vontade de mostrar a outras pessoas.
4. CRIATIVIDADE: priorize invenções inteligentes, soluções inesperadas e objetos pouco conhecidos.
5. POTENCIAL DE DESCOBERTA: dê preferência a produtos que não sejam facilmente encontrados em qualquer loja tradicional.

Regras obrigatórias:
- Seja extremamente seletivo. Qualidade acima de quantidade.
- Não aprove produtos apenas porque são baratos, populares ou estão em promoção.
- Rejeite produtos genéricos, repetitivos, convencionais ou sem diferencial evidente.
- Não aprove um produto comum por causa de nome ou descrição exagerados.
- Não estabeleça limite de preço: o diferencial é mais importante que o valor.
- Não confunda aparência diferente com inovação real.
- Não invente características nem presuma que o produto é raro ou inédito sem evidências.
- Se o nome não der informação suficiente para avaliar, marque PENDENTE.

Classificação:
APROVADO: produto claramente diferenciado, criativo e com forte potencial de despertar curiosidade.
REPROVADO: produto comum, genérico, repetitivo ou sem diferencial relevante.
PENDENTE: informação insuficiente para decidir com segurança.

Para cada produto, informe o status, uma justificativa objetiva e o diferencial (vazio se não houver).

Produtos:
{lista}

Responda APENAS com JSON no formato {{"analise": {{"<id>": {{"status": "APROVADO|REPROVADO|PENDENTE", "justificativa": "...", "diferencial": "..."}}, ...}}}} para todos os ids."""


def classificar_whatsapp(ofertas, lote=20):
    """Devolve {id: {status, justificativa, diferencial}} pelos critérios do canal.
    Sem IA disponível, devolve {} e ninguém é aprovado (falha fechada: nada é enviado)."""
    if not config.GROQ_API_KEY or not ofertas:
        return {}
    analise = {}
    for i in range(0, len(ofertas), lote):
        if i:
            time.sleep(6)
        parte = ofertas[i:i + lote]
        lista = "\n".join(f'- id {o["id"]}: {o["nome"][:110]}' for o in parte)
        try:
            bruto = legenda._chamar_groq(PROMPT_WHATSAPP.format(lista=lista))
            dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
            for k, v in (dados.get("analise") or {}).items():
                status = str((v or {}).get("status", "")).upper().strip()
                if status in ("APROVADO", "REPROVADO", "PENDENTE"):
                    analise[str(k)] = {
                        "status": status,
                        "justificativa": str(v.get("justificativa", ""))[:300],
                        "diferencial": str(v.get("diferencial", ""))[:200],
                    }
        except Exception as e:
            print(f"⚠️  Análise do WhatsApp falhou neste lote ({e}).")
    return analise


# ---------------------------------------------------------------- a foto chama atenção?
PROMPT_FOTO = """Você escolhe produtos para o feed do Instagram {marca} (público: {publico}).
Abaixo vêm {n} fotos de produtos, na ordem, cada uma com o nome. Imagine alguém rolando o feed
rápido. Dê uma nota de 0 a 10 para cada foto:
- 8-10: a foto mostra um produto diferente e atraente, dá para entender na hora o que é e dá
  vontade de ver mais (efeito visual, produto em uso, algo curioso).
- 5-7: dá para entender, mas é sem graça ou parece produto comum de qualquer loja.
- 0-4: foto confusa, cheia de texto/montagem, só embalagem, produto pequeno demais, ou a foto
  não bate com o nome.

{nomes}

Responda APENAS com JSON: {{"fotos": {{"1": <nota>, "2": <nota>, ...}}}}"""

FOTOS_POR_CHAMADA = 6
FOTO_MAX_SEGUNDOS = 420


def notas_foto(ofertas):
    """{id: nota da foto} pelo Gemini (visão). Sem chave ou com o Gemini fora, devolve {} e nada muda."""
    import os
    from . import radar_virais
    if not (os.getenv("GEMINI_API_KEY") or "").strip() or not ofertas:
        return {}
    inicio, notas = time.time(), {}
    for i in range(0, len(ofertas), FOTOS_POR_CHAMADA):
        if time.time() - inicio > FOTO_MAX_SEGUNDOS:
            print("⚠️  Gemini lento: o resto dos produtos fica só com a nota do nome.")
            break
        parte = [(o, radar_virais._foto_b64(o["imagem"])) for o in ofertas[i:i + FOTOS_POR_CHAMADA]]
        parte = [(o, f) for o, f in parte if f]
        if not parte:
            continue
        nomes = "\n".join(f"{k}. {o['nome'][:90]}" for k, (o, _) in enumerate(parte, 1))
        texto = PROMPT_FOTO.format(marca=config.NOME_MARCA, publico=config.PUBLICO, n=len(parte), nomes=nomes)
        dados = _gemini_json(texto, [f for _, f in parte])
        for k, (o, _) in enumerate(parte, 1):
            try:
                notas[o["id"]] = max(0.0, min(10.0, float((dados.get("fotos") or {}).get(str(k)))))
            except (TypeError, ValueError):
                pass
    return notas


def _gemini_json(texto, fotos):
    import os
    import requests
    from . import radar_virais as rv
    chave = os.getenv("GEMINI_API_KEY").strip()
    partes = [{"text": texto}] + [{"inline_data": {"mime_type": "image/jpeg", "data": f.split(",", 1)[1]}}
                                   for f in fotos]
    modelos = rv._modelos_gemini(chave)
    while modelos:
        modelo = modelos[0]
        try:
            r = requests.post(f"{rv.GEMINI_URL}/models/{modelo}:generateContent", params={"key": chave},
                              timeout=60, json={"contents": [{"parts": partes}],
                                                "generationConfig": {"temperature": 0.2,
                                                                     "responseMimeType": "application/json"}})
            if r.status_code == 429 and "PerMinute" in r.text:
                espera = re.search(r'"retryDelay": "(\d+)', r.text)
                time.sleep(min(int(espera.group(1)) if espera else 30, 60) + 2)
                r = requests.post(f"{rv.GEMINI_URL}/models/{modelo}:generateContent", params={"key": chave},
                                  timeout=60, json={"contents": [{"parts": partes}],
                                                    "generationConfig": {"temperature": 0.2,
                                                                         "responseMimeType": "application/json"}})
            if r.status_code != 200:
                print(f"   ⚠️  foto/Gemini {modelo}: HTTP {r.status_code} → próximo modelo")
                modelos.pop(0)
                continue
            bruto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
        except requests.exceptions.Timeout:
            print(f"   ⚠️  foto/Gemini {modelo}: demorou demais → próximo modelo")
            modelos.pop(0)
        except Exception as e:
            print(f"   ⚠️  foto/Gemini {modelo}: {str(e)[:120]}")
            return {}
    return {}
