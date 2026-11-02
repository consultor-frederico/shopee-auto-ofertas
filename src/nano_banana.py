"""Nano Banana (imagem do Gemini) — só para o CENÁRIO em volta do produto (02/11/2026, escolha do Fred).

Regra: a foto do vendedor nunca passa pela IA. O cenário é gerado vazio (sem produto, sem gente, sem texto) e a
foto entra por cima, igual, num cartão branco. DESLIGADO por padrão (NANO_BANANA=1 liga, depois do ok do Fred).
Usa a mesma chave do radar (segredo GEMINI_API_KEY)."""
import base64
import io
import os
import re

import requests
from PIL import Image

URL = "https://generativelanguage.googleapis.com/v1beta"
RESERVA = ("gemini-2.5-flash-image", "gemini-2.5-flash-image-preview", "gemini-2.0-flash-preview-image-generation")


def ligado():
    return os.getenv("NANO_BANANA", "0") == "1" and bool(_chave())


def _chave():
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def modelos():
    """Modelos de imagem que a chave enxerga (NANO_BANANA_MODELO primeiro, se tiver)."""
    nomes = []
    try:
        r = requests.get(f"{URL}/models", params={"key": _chave(), "pageSize": 1000}, timeout=30)
        nomes = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "image" in m["name"] and "generateContent" in (m.get("supportedGenerationMethods") or [])]
    except Exception as e:
        print(f"   ⚠️  Nano Banana: não listou os modelos ({e})")
    pedido = os.getenv("NANO_BANANA_MODELO", "").strip()
    ordem = sorted(nomes, key=lambda n: ("preview" in n, "2.0" in n, n))
    return list(dict.fromkeys(([pedido] if pedido else []) + ordem + [n for n in RESERVA if not nomes]))


def gerar(prompt, proporcao="4:5", log=print):
    """Imagem do Nano Banana (PIL) ou None. Tenta os modelos em ordem e diz por que cada um recusou."""
    if not _chave():
        log("   ⏸️  Nano Banana: sem GEMINI_API_KEY")
        return None
    for modelo in modelos():
        for cfg in ({"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": proporcao}},
                    {"responseModalities": ["TEXT", "IMAGE"]}):
            try:
                r = requests.post(f"{URL}/models/{modelo}:generateContent", params={"key": _chave()}, timeout=120,
                                  json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg})
            except Exception as e:
                log(f"   ⚠️  Nano Banana {modelo}: {e}")
                break
            if r.status_code == 400 and "imageConfig" in cfg:
                continue   # modelo antigo não aceita proporção: tenta sem
            if r.status_code != 200:
                cota = re.findall(r'"quotaId": "([^"]+)"', r.text)[:2]
                log(f"   ⚠️  Nano Banana {modelo}: HTTP {r.status_code} {cota or r.text[:200]}")
                break
            dados = r.json()
            for c in dados.get("candidates", []):
                for p in (c.get("content") or {}).get("parts", []):
                    b = (p.get("inlineData") or p.get("inline_data") or {}).get("data")
                    if b:
                        uso = dados.get("usageMetadata", {})
                        log(f"   🍌 Nano Banana {modelo}: ok ({uso.get('candidatesTokenCount', '?')} tokens de saída)")
                        return Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB")
            log(f"   ⚠️  Nano Banana {modelo}: respondeu sem imagem {str(dados)[:200]}")
            break
    return None


def prompt_cenario(titulo, paleta="tons marrom escuro, creme e dourado"):
    return (f"Fotografia realista de um ambiente vazio onde alguém usaria: {titulo}. "
            "O ambiente fica SEM o produto, sem nenhum objeto em destaque no centro, sem pessoas, sem mãos, "
            "sem texto, sem letras, sem logotipos e sem marcas. Centro da imagem livre e limpo. "
            f"Luz quente e suave, fundo desfocado (bokeh), aconchegante, {paleta}. Formato vertical.")
