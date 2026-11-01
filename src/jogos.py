"""🎲 Brincadeiras no carrossel do Garimpo VIP (01/11/2026, ideias aprovadas pelo Fred).

Em alguns dias o carrossel das 18:45 (src/achados.py) sai como brincadeira, para o pessoal comentar
(comentário é o que faz o Instagram entregar o post para mais gente):

- "duelo"  → ESSE OU ESSE? Capa com 2 achados lado a lado; a pessoa comenta 1 ou 2.
             Depois vêm os 2 slides normais (QUERO 1 / QUERO 2) e o slide final.
- "preco"  → ADIVINHA O PREÇO. Capa com 1 achado e 3 preços (A, B, C); a resposta é o slide seguinte
             (o slide normal do produto, com o preço). QUERO 1 manda o link.

Os produtos vêm da mesma fila e das mesmas regras do carrossel normal (achados.escolher); o QUERO N, o
espelho no Facebook e a vitrine funcionam igual (o post é registrado como carrossel de achados).
Sem promessa de desconto: o preço é "o que o Zé viu na hora do post".

Dias: JOGOS_DIAS="0:duelo,3:preco" (0 = segunda; padrão segunda = duelo, quinta = preço). JOGOS=0 desliga.
Prévia: python -m src.jogos previa   → data/relatorios/jogos/
"""
import os
import random
import time

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import achados_artes as artes, config, imagem

L, A = 1080, 1350
ANA = config.PERFIL == "ana"
LIGADO = os.getenv("JOGOS", "1") != "0"
QTD = {"duelo": 2, "preco": 1}
ZE = config.RAIZ / "assets" / "ze" / "capa" / "ze_aponta.png"


def dias():
    out = {}
    for parte in (os.getenv("JOGOS_DIAS") or "0:duelo,3:preco").split(","):
        if ":" in parte:
            d, modo = parte.split(":", 1)
            if d.strip().isdigit() and modo.strip() in QTD:
                out[int(d)] = modo.strip()
    return out


def modo_de_hoje(hoje=None):
    """'duelo', 'preco' ou None. Só Garimpo VIP. JOGO=duelo|preco força (para testar)."""
    if ANA or not LIGADO:
        return None
    forcado = (os.getenv("JOGO") or "").strip().lower()
    if forcado in QTD:
        return forcado
    from .garimpar import agora
    return dias().get((hoje or agora()).weekday())


# ---------------------------------------------------------------- artes
def _fundo():
    img = Image.new("RGB", (L, A))
    d = ImageDraw.Draw(img)
    for y in range(A):
        k = y / A
        d.line([(0, y), (L, y)], fill=(int(58 - 26 * k), int(32 - 14 * k), int(14 - 6 * k)))
    return img, d


def _centro(d, y, texto, fonte, cor):
    d.text(((L - d.textlength(texto, font=fonte)) / 2, y), texto, font=fonte, fill=cor)


def _ze(img, alt=300, x=None):
    ze = Image.open(ZE).convert("RGBA")
    ze = ze.resize((int(ze.width * alt / ze.height), alt), Image.LANCZOS)
    zx, zy = (L - ze.width - 30) if x is None else x, A - alt
    sombra = ze.getchannel("A").point(lambda v: int(v * 0.45)).filter(ImageFilter.GaussianBlur(10))
    img.paste(Image.new("RGB", ze.size, (0, 0, 0)), (zx + 8, zy + 6), sombra)
    img.paste(ze, (zx, zy), ze)


def _cartao(img, d, foto, caixa, raio=36):
    x0, y0, x1, y1 = caixa
    d.rounded_rectangle([x0 + 6, y0 + 10, x1 + 6, y1 + 10], raio, fill=(20, 10, 4))
    d.rounded_rectangle([x0, y0, x1, y1], raio, fill=imagem.BRANCO)
    if foto is not None:
        f = ImageOps.contain(foto.convert("RGB"), (x1 - x0 - 40, y1 - y0 - 40), Image.LANCZOS)
        img.paste(f, (x0 + (x1 - x0 - f.width) // 2, y0 + (y1 - y0 - f.height) // 2))


def capa_duelo(itens, destino):
    img, d = _fundo()
    _centro(d, 46, "ESSE OU ESSE?", imagem._fonte(108, "Black"), imagem.DOURADO)
    _centro(d, 170, "qual você levaria?", imagem._fonte(44, "SemiBold"), imagem.BRANCO)
    larg, y0, y1 = 470, 260, 790
    f_t = imagem._fonte(36, "ExtraBold")
    f_p = imagem._fonte(48, "Black")
    for i, it in enumerate(itens[:2]):
        o = it["oferta"]
        x0 = 50 + i * (larg + 40)
        _cartao(img, d, it["foto"], (x0, y0, x0 + larg, y1))
        cx, cy, r = x0 + 60, y0 + 58, 44
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=imagem.DOURADO, outline=imagem.ESCURO, width=6)
        d.text((cx, cy + 2), str(i + 1), font=imagem._fonte(60, "Black"), fill=imagem.ESCURO, anchor="mm")
        y = y1 + 26
        for ln in imagem._quebrar(d, o["titulo"], f_t, larg, max_linhas=2):
            d.text((x0 + (larg - d.textlength(ln, font=f_t)) / 2, y), ln, font=f_t, fill=imagem.BRANCO)
            y += 44
        p = f"R$ {o['preco_fmt']}"
        d.text((x0 + (larg - d.textlength(p, font=f_p)) / 2, y + 8), p, font=f_p, fill=imagem.DOURADO_CLARO)
    r = 62
    d.ellipse((L / 2 - r, (y0 + y1) / 2 - r, L / 2 + r, (y0 + y1) / 2 + r), fill=imagem.ESCURO,
              outline=imagem.DOURADO, width=6)
    d.text((L / 2, (y0 + y1) / 2 + 2), "VS", font=imagem._fonte(54, "Black"), fill=imagem.DOURADO, anchor="mm")
    d.rounded_rectangle([50, A - 150, L - 300, A - 50], 40, fill=imagem.DOURADO)
    f_c = imagem._fonte(46, "Black")
    t = "COMENTA 1 OU 2"
    d.text((50 + (L - 350 - d.textlength(t, font=f_c)) / 2, A - 128), t, font=f_c, fill=imagem.ESCURO)
    _ze(img, 290)
    img.save(destino, "JPEG", quality=90, optimize=True)


def _redondo(v, centavos=0.9):
    """Preço falso com os mesmos centavos do preço de verdade (senão o ",99" entrega a resposta)."""
    return max(4 + centavos, round(v) - 1 + centavos)


def opcoes_preco(preco, rnd=random):
    """3 preços (A, B, C) com o de verdade em posição sorteada. Devolve (lista_float, indice_certo)."""
    p = float(preco)
    c = round(p - int(p), 2)
    padroes = [(0.55, 1.75), (0.6, 1.45), (1.4, 2.0), (0.45, 0.7)]
    for _ in range(10):
        a, b = rnd.choice(padroes)
        falsos = [round(_redondo(p * a, c), 2), round(_redondo(p * b, c), 2)]
        ops = [p] + falsos
        if len({f"{x:.2f}" for x in ops}) == 3 and all(abs(x - p) >= max(3, p * 0.2) for x in falsos):
            break
    else:
        ops = [p, _redondo(p * 0.5) if p > 15 else p + 10, _redondo(p * 1.8) + 10]
    rnd.shuffle(ops)
    return ops, ops.index(p)


def _brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def capa_preco(it, opcoes, destino):
    o = it["oferta"]
    img, d = _fundo()
    _centro(d, 40, "ADIVINHA O PREÇO", imagem._fonte(96, "Black"), imagem.DOURADO)
    _cartao(img, d, it["foto"], (90, 170, L - 90, 700))
    f_t = imagem._fonte(44, "ExtraBold")
    y = 724
    for ln in imagem._quebrar(d, o["titulo"], f_t, L - 160, max_linhas=2):
        _centro(d, y, ln, f_t, imagem.BRANCO)
        y += 52
    f_l = imagem._fonte(54, "Black")
    y = max(y + 20, 850)
    for i, v in enumerate(opcoes):
        x0, x1 = 90, 690
        d.rounded_rectangle([x0, y, x1, y + 96], 48, fill=imagem.BRANCO, outline=imagem.DOURADO, width=5)
        d.ellipse((x0 + 14, y + 12, x0 + 86, y + 84), fill=imagem.DOURADO)
        d.text((x0 + 50, y + 49), "ABC"[i], font=imagem._fonte(46, "Black"), fill=imagem.ESCURO, anchor="mm")
        d.text((x0 + 120, y + 18), _brl(v), font=f_l, fill=imagem.ESCURO)
        y += 118
    f_r = imagem._fonte(34, "SemiBold")
    for i, t in enumerate(("chuta nos", "comentários", "e arrasta pra", "ver a resposta")):
        d.text((720, y - 354 + i * 44), t, font=f_r, fill=imagem.DOURADO_CLARO)
    _ze(img, 270)
    img.save(destino, "JPEG", quality=90, optimize=True)


# ---------------------------------------------------------------- carrossel
def gerar(modo, itens, pasta, v=0):
    """Slides do jogo em `pasta`. Devolve o dict no formato do achados.gerar (o achados.publicar posta)."""
    from . import achados
    pasta.mkdir(parents=True, exist_ok=True)
    marca = int(time.time())
    arqs = []
    extra = {}
    capa = f"jogo-{marca}-capa.jpg"
    if modo == "duelo":
        capa_duelo(itens, pasta / capa)
    else:
        ops, certo = opcoes_preco(itens[0]["oferta"]["preco"])
        capa_preco(itens[0], ops, pasta / capa)
        extra = {"opcoes": [_brl(x) for x in ops], "certo": "ABC"[certo]}
    arqs.append(capa)
    for i, it in enumerate(itens, 1):
        nome = f"jogo-{marca}-{i}.jpg"
        achados.slide_produto(it["oferta"], it["foto"], i, pasta / nome, v)
        arqs.append(nome)
    nome = f"jogo-{marca}-fim.jpg"
    artes.final_garimpo(v, len(itens), v).save(pasta / nome, quality=92)
    arqs.append(nome)
    return {"arquivos": arqs, "clipe": None, "story": None, "short": None, "tiktok": [], "legenda_tiktok": "",
            "jogo": modo, **extra,
            "itens": [{k: it["oferta"].get(k) for k in ("id", "nome", "titulo", "preco_fmt", "link_afiliado",
                                                       "plataforma", "imagem", "num")} for it in itens]}


def legenda(modo, itens, info):
    from .achados import _curto
    from .ze import HASHTAGS
    if modo == "duelo":
        a, b = itens[0]["oferta"], itens[1]["oferta"]
        linhas = ["ESSE OU ESSE? 🤠⚔️",
                  "O Zé garimpou os dois e não consegue escolher. Qual você levaria?", "",
                  f"1️⃣ {_curto(a['titulo'])} — R$ {a['preco_fmt']}",
                  f"2️⃣ {_curto(b['titulo'])} — R$ {b['preco_fmt']}", "",
                  "👇 Comenta 1 ou 2!",
                  "Gostou? Comenta QUERO 1 ou QUERO 2 que o Zé te manda o link no direct."]
    else:
        o = itens[0]["oferta"]
        ops = info.get("opcoes", [])
        linhas = ["ADIVINHA O PREÇO! 🤠💰",
                  f"Quanto você acha que custa esse achado: {_curto(o['titulo'])}?", ""]
        linhas += [f"{'ABC'[i]}) {p}" for i, p in enumerate(ops)]
        linhas += ["", "👇 Chuta A, B ou C nos comentários antes de arrastar! A resposta tá no próximo slide.",
                   "Gostou? Comenta QUERO 1 que o Zé te manda o link no direct."]
    if config.LEMBRETE_BIO:
        linhas.append(config.LEMBRETE_BIO)
    linhas += ["", "Preço que o Zé viu na hora do post — pode mudar na loja. Links de afiliado: você paga o mesmo.",
               "", HASHTAGS]
    return "\n".join(linhas)


def previa():
    """Gera os dois jogos com produtos da fila (sem postar) em data/relatorios/jogos/."""
    from . import achados
    from .garimpar import carregar_fila
    pasta = config.RAIZ / "data" / "relatorios" / "jogos"
    itens = achados.escolher(carregar_fila(), conferir=False)
    for modo in QTD:
        if len(itens) < QTD[modo]:
            print(f"⚠️  {modo}: só {len(itens)} produto(s) com foto na fila.")
            continue
        info = gerar(modo, itens[:QTD[modo]], pasta)
        (pasta / f"{modo}-legenda.txt").write_text(legenda(modo, itens[:QTD[modo]], info), encoding="utf-8")
        print(f"✅ {modo}: {', '.join(info['arquivos'])}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "previa":
        previa()
