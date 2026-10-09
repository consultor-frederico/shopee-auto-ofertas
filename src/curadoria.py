"""Curadoria: nota de "fator uau" pela IA e detecção de produtos repetidos/parecidos."""
import json
import re
import unicodedata

from . import config, legenda

PROMPT_UAU = """Você é curador de uma página de achadinhos da Shopee chamada Garimpo VIP.
Dê uma nota de 0 a 10 para o "fator uau" de cada produto: o quanto ele é DIFERENTE,
criativo ou surpreendente, resolve um problema de um jeito esperto, ou dá vontade de comprar
só de ver a foto.

Notas BAIXAS (0-4): itens básicos, de reposição ou commodity — camiseta/calça básica, meia,
cueca, tapete higiênico, papel, sacos, cabos simples, capinha comum, refil, produto de higiene
comum, material escolar simples.
Notas MÉDIAS (5-6): úteis e bem vendidos, mas comuns.
Notas ALTAS (7-10): gadgets curiosos, soluções criativas para casa/carro/pet, itens com efeito
visual, "não sabia que precisava disso", presentes legais.

Produtos:
{lista}

Responda APENAS com JSON no formato {{"notas": {{"<id>": <nota>, ...}}}} para todos os ids."""


def _norm(txt):
    txt = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode().lower()
    return [t for t in re.findall(r"[a-z0-9]+", txt) if len(t) > 2]


PARADAS = {"com", "para", "kit", "unidades", "und", "pcs", "original", "promocao", "envio",
           "imediato", "novo", "nova", "pronta", "entrega", "atacado", "qualidade", "alta"}


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
        parte = ofertas[i:i + lote]
        lista = "\n".join(f'- id {o["id"]}: {o["nome"][:110]}' for o in parte)
        try:
            bruto = legenda._chamar_groq(PROMPT_UAU.format(lista=lista))
            dados = json.loads(re.search(r"\{.*\}", bruto, re.S).group(0))
            for k, v in (dados.get("notas") or {}).items():
                try:
                    notas[str(k)] = max(0.0, min(10.0, float(v)))
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            print(f"⚠️  Curadoria por IA falhou neste lote ({e}).")
    return notas
