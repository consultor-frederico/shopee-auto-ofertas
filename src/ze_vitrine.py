"""Reels do Zé com produtos (ok do Fred em 02/11/2026: "o Zé vem, normal, mas tem que ter produto na capa").

O Zé aparece em tela cheia por 2 s (o gancho, que é o que dá alcance), encolhe para um quadro dourado no
canto de baixo e 3 produtos do dia entram deslizando por cima, cada um com o "QUERO N". A frase do roteiro
(assets/ze/textos.json) fica no alto enquanto ele está grande e depois vira um balão ao lado dele.
A capa do Reels (thumb_offset) é um quadro com o 1º produto, para o perfil mostrar produto.
Os produtos saem da fila como postados (não repetem no carrossel da noite) e o Reels entra em top.json,
então "QUERO 2" nos comentários manda o link do 2º no direct.

Desliga com ZE_VITRINE=0 (volta o Reels só com o Zé). Sem 3 produtos bons, sai o Reels normal.

Prévia: python -m src.ze_vitrine ze_salario_semtrilha.mp4   → data/relatorios/ze_vitrine/
"""
import json
import os
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import config, imagem, ze, ze_textos

LIGADO = os.getenv("ZE_VITRINE", "1") != "0" and config.PERFIL == "garimpo"
QTD = 3
W, H = 1080, 1920
GANCHO = 2.0          # segundos do Zé em tela cheia
ENCOLHE = 0.45        # animação dele indo para o canto
SEG_PROD = 2.0        # cada produto na tela
ENTRA = 0.3           # produto deslizando
INICIO_PRODUTOS = GANCHO + ENCOLHE - 0.1
CAPA_MS = int((INICIO_PRODUTOS + 1.0) * 1000)   # capa do Reels: o 1º produto já parado na tela
CX, CY, CW = 150, 150, 780            # cartão do produto (4:5)
CH = CW * 5 // 4
ZW = 330                              # Zé pequeno (9:16)
ZH = ZW * 16 // 9
ZX, ZY = 56, 1165
MARROM = (45, 28, 12)
DOURADO = "#E2BE68"
NUM = ["1️⃣", "2️⃣", "3️⃣"]


# ---------------------------------------------------------------- camadas
def _fundo(destino):
    img = Image.new("RGB", (W, H), MARROM)
    d = ImageDraw.Draw(img)
    for i in range(0, H, 4):   # degradê marrom
        k = i / H
        d.rectangle([0, i, W, i + 4], fill=(int(58 - 26 * k), int(37 - 17 * k), int(17 - 8 * k)))
    halo = Image.new("L", (W, H), 0)   # brilho dourado atrás do cartão
    ImageDraw.Draw(halo).ellipse([CX - 120, CY - 80, CX + CW + 120, CY + CH + 80], fill=70)
    img = Image.composite(Image.new("RGB", (W, H), (226, 190, 104)), img, halo.filter(ImageFilter.GaussianBlur(90)))
    img.save(destino)


def _cartao(slide, destino):
    """Slide 4:5 do produto com cantos redondos, borda dourada e sombra. Devolve a margem da sombra."""
    m = 40
    img = Image.new("RGBA", (CW + 2 * m, CH + 2 * m), (0, 0, 0, 0))
    sombra = Image.new("L", img.size, 0)
    ImageDraw.Draw(sombra).rounded_rectangle([m, m + 14, m + CW, m + CH + 14], 36, fill=150)
    img.putalpha(sombra.filter(ImageFilter.GaussianBlur(18)))
    foto = Image.open(slide).convert("RGB").resize((CW, CH), Image.LANCZOS)
    mask = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, CW - 1, CH - 1], 34, fill=255)
    img.paste(foto, (m, m), mask)
    ImageDraw.Draw(img).rounded_rectangle([m, m, m + CW - 1, m + CH - 1], 34, outline=DOURADO, width=6)
    img.save(destino)
    return m


def _moldura(destino, placa):
    """Quadro dourado atrás do Zé pequeno; a plaquinha ZÉ GARIMPO vai por cima dele."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    b = 7
    ImageDraw.Draw(img).rounded_rectangle([ZX - b, ZY - b, ZX + ZW + b, ZY + ZH + b], 22, fill=DOURADO)
    img.save(destino)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = imagem._fonte(34, "Black")
    t = "ZÉ GARIMPO"
    tw = d.textlength(t, font=f)
    px, py = ZX + (ZW - tw) / 2 - 22, ZY + ZH - 30
    d.rounded_rectangle([px, py, px + tw + 44, py + 58], 29, fill=MARROM, outline=DOURADO, width=4)
    d.text((px + 22, py + 9), t, font=f, fill=DOURADO)
    img.save(placa)


def _balao(texto, destino):
    """Balão de fala à direita do Zé, longe da coluna de botões do Instagram."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, x1 = ZX + ZW + 46, W - 150
    tam = 60
    while True:
        f = imagem._fonte(tam, "Black")
        linhas = ze_textos._quebrar(d, texto, f, x1 - x0 - 70)
        if len(linhas) <= 3 or tam <= 40:
            break
        tam -= 4
    alt = int(tam * 1.2)
    y0 = ZY + 70
    creme = (255, 250, 238)
    d.rounded_rectangle([x0, y0, x1, y0 + alt * len(linhas) + 64], 36, fill=creme, outline=DOURADO, width=6)
    d.polygon([(x0 + 4, y0 + 50), (x0 - 40, y0 + 90), (x0 + 4, y0 + 100)], fill=creme)
    d.line([(x0, y0 + 50), (x0 - 40, y0 + 90), (x0, y0 + 100)], fill=DOURADO, width=6)
    for i, l in enumerate(linhas):
        cor = (150, 105, 30) if i == len(linhas) - 1 and len(linhas) > 1 else MARROM
        d.text(((x0 + x1 - d.textlength(l, font=f)) / 2, y0 + 32 + i * alt), l, font=f, fill=cor)
    img.save(destino)


# ---------------------------------------------------------------- vídeo
def gravar(video, slides, saida):
    """Monta o Reels (1080x1920) com o vídeo do Zé e os slides dos produtos, e põe a música."""
    video, saida = Path(video), Path(saida)
    tmp = saida.with_name(saida.stem + "_camadas")
    tmp.mkdir(parents=True, exist_ok=True)
    dur_ze = ze._duracao(video)
    total = max(dur_ze, INICIO_PRODUTOS + SEG_PROD * len(slides))
    _fundo(tmp / "fundo.png")
    _moldura(tmp / "moldura.png", tmp / "placa.png")
    m = 0
    for i, s in enumerate(slides):
        m = _cartao(s, tmp / f"card{i}.png")
    frases = ze_textos.frases(video.name)
    for i, (_, _, t) in enumerate(frases):
        ze_textos.cartela(t, tmp / f"cartela{i}.png")
        _balao(t, tmp / f"balao{i}.png")

    fixa = ["-loop", "1", "-t", f"{total:.2f}", "-i"]
    ent = [*fixa, str(tmp / "fundo.png"), "-i", str(video), *fixa, str(tmp / "moldura.png"),
           *fixa, str(tmp / "placa.png")]
    n = 4
    idx_card, idx_cart, idx_bal = [], [], []
    for i in range(len(slides)):
        ent += [*fixa, str(tmp / f"card{i}.png")]
        idx_card.append(n)
        n += 1
    for i in range(len(frases)):
        ent += [*fixa, str(tmp / f"cartela{i}.png"), *fixa, str(tmp / f"balao{i}.png")]
        idx_cart.append(n)
        idx_bal.append(n + 1)
        n += 2

    p = f"(1-pow(1-clip((t-{GANCHO})/{ENCOLHE},0,1),3))"   # 0 → 1 enquanto ele encolhe (suavizado)
    pequeno = GANCHO + ENCOLHE
    filtro = (f"[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,"
              f"tpad=stop_mode=clone:stop_duration={max(0, total - dur_ze) + 0.1:.2f},"
              f"scale=w='trunc((1080-(1080-{ZW})*{p})/2)*2':h='trunc((1920-(1920-{ZH})*{p})/2)*2':eval=frame[ze];"
              f"[0:v]fps=30,format=rgba[bg];")
    ult = "bg"
    for i, k in enumerate(idx_card):   # cada produto entra deslizando da direita e fica até o próximo
        t0 = INICIO_PRODUTOS + i * SEG_PROD
        x = f"if(lt(t,{t0 + ENTRA}),{CX - m}+({W}-{CX - m})*pow(1-(t-{t0})/{ENTRA},2),{CX - m})"
        filtro += f"[{ult}][{k}:v]overlay=x='{x}':y={CY - m}:eval=frame:enable='gte(t,{t0})'[c{i}];"
        ult = f"c{i}"
    filtro += (f"[{ult}][2:v]overlay=0:0:enable='gte(t,{pequeno})'[mo];"
               f"[mo][ze]overlay=x='{ZX}*{p}':y='{ZY}*{p}':eval=frame[z];"
               f"[z][3:v]overlay=0:0:enable='gte(t,{pequeno})'[zp];")
    ult = "zp"
    for i, (a, b, _) in enumerate(frases):   # frase no alto com ele grande; depois vira balão
        fim = total if i == len(frases) - 1 else b
        filtro += (f"[{ult}][{idx_cart[i]}:v]overlay=0:0:enable='between(t,{a},{min(b, GANCHO)})*lt(t,{GANCHO})'[t{i}];"
                   f"[t{i}][{idx_bal[i]}:v]overlay=0:0:enable='between(t,{max(a, pequeno)},{fim})'[u{i}];")
        ult = f"u{i}"
    filtro += f"[{ult}]format=yuv420p[v];[1:a]aresample=44100,aformat=channel_layouts=stereo,apad=whole_dur={total:.2f}[a]"
    bruto = tmp / "bruto.mp4"
    try:
        subprocess.run([ze._ffmpeg(), "-y", "-loglevel", "error", *ent, "-filter_complex", filtro,
                        "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium",
                        "-crf", "20", "-profile:v", "high", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                        str(bruto)], check=True)
        musicas = ze.escolher_musicas({"id": video.name}, total) if ze.MUSICA_LIGADA and "comtrilha" not in video.name else []
        try:
            if musicas:
                ze._com_musica(str(bruto), musicas, str(saida))
                print(f"🎵 Música: {' → '.join(x.stem for x in musicas)}")
        except Exception as e:
            print(f"::warning::Música não entrou ({e}); o vídeo sai só com a voz.")
        if not saida.exists():
            bruto.replace(saida)
    finally:
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()


# ---------------------------------------------------------------- produtos
def escolher_produtos():
    """Os 3 achados mais "uau" da fila (mesmas regras do carrossel: preço e foto conferidos, famílias diferentes)."""
    from . import achados, numeros
    from .garimpar import carregar_fila, salvar_fila
    fila = carregar_fila()
    itens = achados.escolher(fila)
    salvar_fila(fila)   # guarda o que foi descartado na conferência de preço
    itens.sort(key=lambda it: (it["oferta"].get("uau") or 0, it["oferta"].get("vendas") or 0), reverse=True)
    itens = itens[:QTD]
    if len(itens) < QTD:
        return []
    for it in itens:
        numeros.numerar(it["oferta"])
    salvar_fila(fila)
    return itens


def preparar(video, saida):
    """Gera o Reels com produtos em `saida`. Devolve a lista de itens (para o registro do QUERO N) ou None."""
    from . import achados
    itens = escolher_produtos()
    if not itens:
        print("⚠️  Menos de 3 produtos bons na fila: sai o Reels só com o Zé.")
        return None
    saida = Path(saida)
    slides = []
    for i, it in enumerate(itens, 1):
        s = saida.with_name(f"{saida.stem}-p{i}.jpg")
        achados.slide_produto(it["oferta"], it["foto"], i, s)
        slides.append(s)
    try:
        gravar(video, slides, saida)
    finally:
        for s in slides:
            s.unlink(missing_ok=True)
    for i, it in enumerate(itens, 1):
        print(f"🛍️  {i}. {it['oferta']['titulo'][:60]} — R$ {it['oferta']['preco_fmt']}")
    return [{k: it["oferta"].get(k) for k in ("id", "nome", "titulo", "preco_fmt", "link_afiliado", "plataforma",
                                               "imagem", "num")} for it in itens]


def legenda(itens, abertura):
    linhas = [abertura, "", f"🛍️ Os {len(itens)} achados do Zé de hoje:"]
    linhas += [f"{NUM[i]} {achados_curto(it)} — R$ {it['preco_fmt']}" for i, it in enumerate(itens)]
    linhas += ["", "👇 Comenta QUERO + o número (ex.: QUERO 2) que o Zé te manda o link no direct!"]
    if config.LEMBRETE_BIO:
        linhas.append(config.LEMBRETE_BIO)
    linhas += ["", "Preços conferidos na hora do post — podem mudar na loja. Links de afiliado: você paga o mesmo.",
               "", ze.HASHTAGS]
    return "\n".join(linhas)


def achados_curto(it):
    from .achados import _curto
    return _curto(it.get("titulo") or it.get("nome") or "")


COMENTARIO = "Gostou de algum? Comenta QUERO + o número (QUERO 1, 2 ou 3) que o Zé te manda o link no direct 👇🤠"


def registrar(media_id, permalink, itens, fb_post=None):
    """Reels entra em top.json (o responder atende "QUERO N") e os produtos saem da fila como postados."""
    from .garimpar import FMT, agora, carregar_fila, salvar_fila
    arq = config.PASTA_PERFIL / "top.json"
    agora_s = agora().strftime(FMT)
    dados = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"posts": {}}
    dados["posts"][media_id] = {"tipo": "achados", "titulo": "Reels do Zé", "rotulo": agora().strftime("%d/%m"),
                                "itens": itens, "postado_em": agora_s, "permalink": permalink,
                                **({"fb_post": fb_post} if fb_post else {})}
    limite = (agora() - timedelta(days=60)).strftime(FMT)
    dados["posts"] = {k: v for k, v in dados["posts"].items() if v.get("postado_em", "") >= limite}
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    fila = carregar_fila()
    for it in itens:
        o = fila["ofertas"].get(it["id"])
        if o:
            o.update({"status": "postado", "formato": "ze_vitrine", "postado_em": agora_s,
                      "postado_ts": time.time(), "achados_post": media_id, "permalink": permalink})
    salvar_fila(fila)


def guardar_fb(media_id, fb_post):
    arq = config.PASTA_PERFIL / "top.json"
    dados = json.loads(arq.read_text(encoding="utf-8"))
    if media_id in dados["posts"]:
        dados["posts"][media_id]["fb_post"] = fb_post
        arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":   # prévia com slides já prontos (sem fila): python -m src.ze_vitrine VIDEO [SLIDE ...]
    pasta = config.RAIZ / "data" / "relatorios" / "ze_vitrine"
    pasta.mkdir(parents=True, exist_ok=True)
    nome = sys.argv[1] if len(sys.argv) > 1 else "ze_salario_semtrilha.mp4"
    slides = [Path(s) for s in sys.argv[2:]]
    gravar(ze.PASTA / nome, slides, pasta / nome)
    print(f"✅ {pasta / nome}")
