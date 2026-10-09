"""Post de chamada no Instagram para o canal do Telegram (terças e sextas).

  python -m src.chamada preparar   → gera a arte em site/ (vai para o GitHub Pages)
  python -m src.chamada publicar   → publica no Instagram
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageOps

from . import config, instagram
from .garimpar import BRT, FMT, agora, carregar_fila
from .imagem import BRANCO, CINZA, DOURADO, DOURADO_CLARO, ESCURO, _fonte

PASTA_SITE = config.RAIZ / "site"
ARQ_PROX = config.PASTA_DADOS / "proxima_chamada.json"
CANAL = "t.me/garimpovipofertas"
L, A = 1080, 1350

TITULOS = [
    ("CUPONS E OFERTAS", "EXTRAS NO TELEGRAM"),
    ("TEM OFERTA QUE", "NÃO CABE AQUI"),
    ("QUER O LINK", "SEM PRECISAR PEDIR?"),
]

LEGENDAS = [
    "🎟️ Cupons, campanhas e MUITO mais achadinhos estão no nosso canal do Telegram!\n"
    "Lá as ofertas chegam o dia todo, com link direto, sem precisar comentar. 💎\n\n"
    "👉 Toque no link da bio e entre no canal Garimpo VIP.",
    "📣 Aqui no Instagram vão só os melhores… mas no Telegram vai TUDO que a gente garimpa! 🔥\n"
    "Cupons da Shopee, campanhas relâmpago e dezenas de achadinhos por dia.\n\n"
    "👉 Link na bio: canal Garimpo VIP no Telegram.",
    "💬 Cansou de comentar EU QUERO? No nosso canal do Telegram o link já vem pronto, é só tocar! 🛒\n"
    "E quando a Shopee solta cupom, quem está lá fica sabendo primeiro. 🎟️\n\n"
    "👉 Entre pelo link da bio.",
]

HASHTAGS = "#achadinhos #shopee #cupons #ofertas #promoção #garimpovip"


def _saida(chave, valor):
    arq = os.getenv("GITHUB_OUTPUT")
    if arq:
        with open(arq, "a") as f:
            f.write(f"{chave}={valor}\n")


def ofertas_na_semana(fila):
    limite = agora() - timedelta(days=7)
    n = 0
    for o in fila["ofertas"].values():
        quando = o.get("telegram_em") or (o.get("postado_em") if o.get("telegram") == "ok" else "")
        if quando and datetime.strptime(quando, FMT).replace(tzinfo=BRT) >= limite:
            n += 1
    return n


def gerar_arte(destino, variante, n_semana):
    img = Image.new("RGB", (L, A), "#EEEDE9")
    d = ImageDraw.Draw(img)
    try:
        logo = Image.open(config.LOGO).convert("RGBA")
        logo = ImageOps.contain(logo, (420, 250), Image.LANCZOS)
        img.paste(logo, ((L - logo.width) // 2, 60), logo)
    except Exception:
        pass
    # bilhete (cupom) estilizado
    x0, y0, x1, y1 = 90, 350, L - 90, 900
    d.rounded_rectangle([x0, y0, x1, y1], 40, fill=ESCURO)
    for cx in (x0, x1):
        d.ellipse([cx - 45, (y0 + y1) // 2 - 45, cx + 45, (y0 + y1) // 2 + 45], fill="#EEEDE9")
    for yy in range(y0 + 40, y1 - 30, 34):
        d.line([x1 - 170, yy, x1 - 170, yy + 16], fill=DOURADO, width=4)
    t1, t2 = TITULOS[variante % len(TITULOS)]
    largura = (x1 - 170) - x0 - 110

    def caber(txt, tam, peso):
        while tam > 30 and d.textlength(txt, font=_fonte(tam, peso)) > largura:
            tam -= 2
        return _fonte(tam, peso)
    f1, f2 = caber(t1, 64, "Black"), caber(t2, 52, "ExtraBold")
    cx = (x0 + x1 - 170) / 2
    d.text((cx - d.textlength(t1, font=f1) / 2, y0 + 160), t1, font=f1, fill=BRANCO)
    d.text((cx - d.textlength(t2, font=f2) / 2, y0 + 250), t2, font=f2, fill=DOURADO_CLARO)
    fp = _fonte(38, "SemiBold")
    sub = f"+{n_semana} achadinhos esta semana" if n_semana >= 20 else "achadinhos o dia todo"
    d.text((cx - d.textlength(sub, font=fp) / 2, y0 + 350), sub, font=fp, fill="#CFC6B8")
    f3 = _fonte(92, "Black")
    d.text((x1 - 105 - d.textlength("%", font=f3) / 2, (y0 + y1) / 2 - 60), "%", font=f3, fill=DOURADO)
    # rodapé
    f4, f5 = _fonte(50, "ExtraBold"), _fonte(40, "SemiBold")
    t = "ENTRE PELO LINK DA BIO"
    d.text(((L - d.textlength(t, font=f4)) / 2, 990), t, font=f4, fill=ESCURO)
    d.text(((L - d.textlength(CANAL, font=f5)) / 2, 1065), CANAL, font=f5, fill=CINZA)
    d.rectangle([0, A - 130, L, A], fill=ESCURO)
    partes = [("CANAL ", BRANCO), ("GARIMPO VIP", DOURADO_CLARO), (" NO TELEGRAM", BRANCO)]
    f6 = _fonte(44, "ExtraBold")
    x = (L - sum(d.textlength(p, font=f6) for p, _ in partes)) / 2
    for p, cor in partes:
        d.text((x, A - 95), p, font=f6, fill=cor)
        x += d.textlength(p, font=f6)
    img.save(destino, "JPEG", quality=90)
    return destino


def preparar():
    _saida("tem_post", "false")
    if not instagram.tem_token():
        print("⏸️  IG_ACCESS_TOKEN ausente.")
        return
    fila = carregar_fila()
    variante = int(time.time() // (3.5 * 86400))  # muda a cada chamada (2x por semana)
    pasta = PASTA_SITE / "midia"
    pasta.mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    (PASTA_SITE / "index.html").write_text("<!doctype html><title>Garimpo VIP</title>Garimpo VIP")
    nome = f"chamada-{int(time.time())}.jpg"
    gerar_arte(pasta / nome, variante, ofertas_na_semana(fila))
    legenda = LEGENDAS[variante % len(LEGENDAS)] + "\n\n" + HASHTAGS
    ARQ_PROX.write_text(json.dumps({"arquivo": f"midia/{nome}", "legenda": legenda}), encoding="utf-8")
    print(f"🎬 Chamada preparada (variante {variante % len(TITULOS)}).")
    _saida("tem_post", "true")


def publicar():
    from .postar import _esperar_url
    prox = json.loads(ARQ_PROX.read_text(encoding="utf-8"))
    url = f"{os.getenv('PAGES_URL', '').rstrip('/')}/{prox['arquivo']}"
    _esperar_url(url)
    ig_id = instagram.conta()["user_id"]
    cont = instagram.criar_container(ig_id, prox["legenda"], imagem_url=url)
    instagram.aguardar_container(cont)
    media = instagram.publicar(ig_id, cont)
    ARQ_PROX.unlink(missing_ok=True)
    print(f"✅ Chamada publicada: {instagram.permalink(media) or media}")


if __name__ == "__main__":
    acao = {"preparar": preparar, "publicar": publicar}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if not acao:
        print("Uso: python -m src.chamada preparar|publicar")
        sys.exit(2)
    try:
        acao()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
