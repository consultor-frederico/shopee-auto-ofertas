"""🎄 Moldura de Natal nas artes do Garimpo VIP (pedido do Fred em 03/11/2026: "até o final de dezembro, depois
volta ao normal").

De 01/11 a 31/12 as artes de produto do Garimpo (post, slides do carrossel e do kit, capa com produto, slide final,
Telegram e kit do WhatsApp) saem dentro de uma moldura natalina: fundo vermelho com neve, pisca-pisca no topo,
etiqueta "NATAL DO ZÉ" e borda dourada. A arte original fica inteira, só um pouco menor. Em janeiro desliga sozinha.
A Ana não muda. Para desligar antes: variável NATAL_ARTE=0.
"""
import math
import os
import random

from PIL import Image, ImageDraw

from . import config

L, A = 1080, 1350
MESES = (11, 12)


def ligado(hoje=None):
    if config.PERFIL == "ana" or os.getenv("NATAL_ARTE", "1") == "0":
        return False
    from .garimpar import agora
    return (hoje or agora()).month in MESES


def neve(d, largura, altura, semente=7, n=140):
    """Flocos de neve sempre no mesmo lugar (a arte não "pisca" de um post para o outro)."""
    rnd = random.Random(semente)
    for _ in range(n):
        x, y, r = rnd.randint(0, largura), rnd.randint(0, altura), rnd.choice((2, 3, 3, 4, 5))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255) if r > 3 else (236, 214, 200))


def moldura(arte):
    """Devolve a arte (PIL) dentro da moldura de Natal, no mesmo tamanho 1080x1350."""
    from . import imagem
    arte = arte.convert("RGB")
    img = Image.new("RGB", (L, A))
    d = ImageDraw.Draw(img)
    for y in range(A):
        k = y / A
        d.line([(0, y), (L, y)], fill=(int(118 - 66 * k), int(16 - 8 * k), int(22 - 12 * k)))
    neve(d, L, A, semente=11, n=90)
    topo, lado, base = 92, 40, 26
    escala = min((L - 2 * lado) / arte.width, (A - topo - base) / arte.height)
    w, h = int(arte.width * escala), int(arte.height * escala)
    x0, y0 = (L - w) // 2, topo + (A - topo - base - h) // 2
    d.rounded_rectangle((x0 - 8, y0 - 8, x0 + w + 8, y0 + h + 8), 22, fill=imagem.DOURADO)
    img.paste(arte.resize((w, h), Image.LANCZOS), (x0, y0))
    # pisca-pisca: fio ondulado com lampadinhas coloridas
    cores = [(255, 70, 70), (255, 214, 90), (90, 220, 120), (90, 170, 255)]
    d.line([(x, 34 + 14 * math.sin(x / 70)) for x in range(-10, L + 11, 6)], fill=(30, 60, 30), width=4)
    for i, x in enumerate(range(30, L, 64)):
        y = 34 + 14 * math.sin(x / 70) + 16
        cor = cores[i % len(cores)]
        d.ellipse((x - 16, y - 10, x + 16, y + 22), fill=tuple(int(c * 0.45) for c in cor))   # brilho
        d.ellipse((x - 9, y - 6, x + 9, y + 18), fill=cor)
        d.rectangle((x - 5, y - 12, x + 5, y - 5), fill=(60, 60, 60))
    fe = imagem._fonte(28, "ExtraBold")
    t = "NATAL DO ZÉ"
    tw = d.textlength(t, font=fe) + 44
    d.rounded_rectangle(((L - tw) / 2, topo - 46, (L + tw) / 2, topo - 8), 19, fill=imagem.DOURADO)
    d.text((L / 2, topo - 27), t, font=fe, fill=imagem.ESCURO, anchor="mm")
    return img


def aplicar(img):
    """Moldura de Natal se estiver na época (e a arte tiver o formato do feed); senão devolve a arte como veio."""
    if not ligado() or img.size != (L, A):
        return img
    try:
        return moldura(img)
    except Exception as e:
        print(f"::warning::Moldura de Natal não saiu ({e}); fica a arte normal.")
        return img
