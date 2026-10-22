"""Curadoria: nota de "fator uau" pela IA e detecção de produtos repetidos/parecidos."""
import json
import re
import time
import unicodedata

from . import config, legenda

PROMPT_UAU = """Você é curador de uma página de achadinhos da Shopee chamada {marca}
(público: {publico}).
Dê uma nota de 0 a 10 para o "fator uau" de cada produto: o quanto ele é DIFERENTE,
criativo ou surpreendente, resolve um problema de um jeito esperto, ou dá vontade de comprar
só de ver a foto.

Notas BAIXAS (0-4): itens básicos, de reposição ou commodity — camiseta/calça básica, meia,
cueca, tapete higiênico, papel, sacos, cabos simples, capinha comum, refil, bobina ou peça de reposição, produto de higiene
comum, material escolar simples.
Notas MÉDIAS (5-6): úteis e bem vendidos, mas comuns — inclusive eletrônico "de vitrine" que todo
mundo já posta: smartwatch, fone, power bank, carregador, aspirador portátil, mochila, lanterna,
caixa de som, ring light. Esses só passam de 6 se tiverem algo realmente inusitado.
Nota 0: produto com nome de franquia, marca ou personagem famoso (filme, série, desenho, anime,
time, grife) — é risco de réplica.
Nota 0 também: produto que não combina com o público acima (ex.: numa página para o público
feminino, brinquedo infantil, ferramenta, isqueiro/acendedor, item automotivo ou masculino).
Notas ALTAS (7-8): gadgets curiosos, soluções criativas para casa/carro/pet, itens com efeito
visual, "não sabia que precisava disso", presentes legais.
Notas 9-10: RARAS — só para o que é realmente surpreendente e quase ninguém conhece
(a pessoa para de rolar o feed para ver). No máximo 1 em cada 10 produtos.

Produtos:
{lista}

Responda APENAS com JSON no formato {{"notas": {{"<id>": <nota>, ...}}}} para todos os ids."""


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


def notas_uau(ofertas, lote=40):
    """Devolve {id: nota}. Sem IA disponível, devolve {} (quem chama decide o padrão)."""
    if not config.GROQ_API_KEY or not ofertas:
        return {}
    notas = {}
    for i in range(0, len(ofertas), lote):
        if i:
            time.sleep(6)   # respeita o limite de tokens por minuto do plano gratuito da Groq
        parte = ofertas[i:i + lote]
        lista = "\n".join(f'- id {o["id"]}: {o["nome"][:110]}' for o in parte)
        try:
            bruto = legenda._chamar_groq(PROMPT_UAU.format(marca=config.NOME_MARCA, publico=config.PUBLICO, lista=lista))
            dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
            for k, v in (dados.get("notas") or {}).items():
                try:
                    notas[str(k)] = max(0.0, min(10.0, float(v)))
                except (TypeError, ValueError):
                    pass
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
