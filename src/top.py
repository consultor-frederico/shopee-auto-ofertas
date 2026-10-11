"""🏆 Top 5 da Semana (sextas) e Top 5 do Mês (último dia do mês) — carrossel no Instagram.

Pega o que mais pediram na Busca do Zé no período (comentários e direct), refaz a busca na Shopee
NA HORA de postar (foto, preço, nota, vendas e link atualizados) e monta 7 slides:
capa com o Zé → 5 produtos → slide final puxando para a Busca do Zé.
Se houver menos de 5 pedidos, completa com as ofertas que mais pediram o link (EU QUERO).
Quem comenta "QUERO 3" recebe o link do 3º; só "QUERO" recebe a lista com os 5 (ver responder.py).

Uso:
  python -m src.top preparar [auto|semana|mes]   → gera os slides em site/midia/top/
  python -m src.top publicar                      → publica o carrossel (precisa do PAGES_URL)
  python -m src.top previa [semana|mes]           → só gera os slides em data/relatorios/top/ (não posta)
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config, instagram
from .garimpar import BRT, FMT, agora, carregar_fila

ARQ_TOP = config.PASTA_PERFIL / "top.json"
PASTA_SITE = config.RAIZ / "site"
ARQ_PROXIMO = config.PASTA_PERFIL / "top_proximo.json"
FONTE = config.RAIZ / "assets" / "fontes" / "Poppins-Bold.ttf"
CAPAS = config.RAIZ / "assets" / "ze" / "top"
QTD = 5
DONOS = {"fredericosn"}          # testes do próprio Fred não entram no ranking
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

W, H = 1080, 1350
AM, BR = (255, 200, 40), (255, 255, 255)
TEMAS = {   # semana: laranja da saída da mina; mês: azul do céu da cena
    "semana": {"fundo": (70, 32, 8), "borda": (45, 20, 5), "mistura": (60, 25, 5), "forca": 0.55},
    "mes": {"fundo": (16, 42, 92), "borda": (15, 35, 80), "mistura": (12, 45, 105), "forca": 0.8},
}
CARD, BEGE, VERDE, VERMELHO = (255, 248, 235), (240, 220, 190), (30, 150, 80), (220, 60, 40)


# ---------------------------------------------------------------- o que entra no Top
def _f(n):
    return ImageFont.truetype(str(FONTE), n)


def periodo(tipo, hoje=None):
    hoje = hoje or agora()
    if tipo == "mes":
        inicio = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return inicio, f"{MESES[hoje.month - 1]} de {hoje.year}"
    inicio = (hoje - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    if inicio.month == hoje.month:
        rotulo = f"{inicio.day:02d} a {hoje.day:02d} de {MESES[hoje.month - 1]}"
    else:
        rotulo = f"{inicio.day:02d}/{inicio.month:02d} a {hoje.day:02d}/{hoje.month:02d}"
    return inicio, rotulo


def _chave(termo):
    from .busca_ze import _palavras
    return {p for p in _palavras(termo) if len(p) > 2}


def pedidos_do_periodo(inicio):
    """[(termo, pessoas)] do mais pedido para o menos; pedidos parecidos contam juntos."""
    from . import busca_ze
    d = busca_ze.carregar()
    desde = inicio.strftime(FMT)
    grupos = []   # {"termo", "chave", "pessoas": set}
    for reg in list(d.get("comentarios", {}).values()) + list(d.get("dms", {}).values()):
        t = (reg.get("termo") or "").strip()
        if not t or reg.get("em", "") < desde or reg.get("status") != "entregue":
            continue
        if (reg.get("usuario") or "").lower() in DONOS:
            continue
        quem = reg.get("autor") or reg.get("usuario") or reg.get("em")
        k = _chave(t)
        for g in grupos:
            if k and g["chave"] and len(k & g["chave"]) / len(k | g["chave"]) >= 0.6:
                g["pessoas"].add(quem)
                break
        else:
            grupos.append({"termo": t, "chave": k, "pessoas": {quem}})
    grupos.sort(key=lambda g: len(g["pessoas"]), reverse=True)
    return [(g["termo"], len(g["pessoas"])) for g in grupos]


def _mais_pedidos_eu_quero(inicio):
    """Plano B: ofertas postadas que mais receberam pedido de link no período."""
    from .responder import carregar_respondidos
    desde = inicio.strftime(FMT)
    cont = {}
    for r in carregar_respondidos().values():
        if r.get("dm") == "ok" and r.get("em", "") >= desde and r.get("oferta"):
            cont[r["oferta"]] = cont.get(r["oferta"], 0) + 1
    fila = carregar_fila()["ofertas"]
    return [(fila[i], n) for i, n in sorted(cont.items(), key=lambda x: -x[1]) if i in fila]


def escolher(tipo):
    from . import busca_ze, precos
    from .imagem import _baixar_foto
    inicio, rotulo = periodo(tipo)
    itens, ids = [], set()

    def cabe(o):
        return o["id"] not in ids and not any(busca_ze._mesmo_produto(o, x["oferta"]) for x in itens)

    for termo, pessoas in pedidos_do_periodo(inicio):
        if len(itens) >= QTD:
            break
        try:
            achados = busca_ze.achados(termo)
        except Exception as e:
            print(f"⚠️  Busca de '{termo}' falhou: {e}")
            continue
        for o in achados:
            if not cabe(o):
                continue
            try:
                foto = _baixar_foto(o["imagem"])
            except Exception as e:
                print(f"⚠️  Foto de {o['id']} não baixou ({e}); tentando outro.")
                continue
            itens.append({"oferta": o, "pedido": termo, "vezes": pessoas, "foto": foto, "origem": "busca"})
            ids.add(o["id"])
            print(f"🔎 '{termo}' ({pessoas} pessoa(s)) → {o['nome'][:60]} — R$ {o['preco_fmt']}")
            break
    if len(itens) < QTD:   # plano B: o que mais pediram o link nos posts
        for o, n in _mais_pedidos_eu_quero(inicio):
            if len(itens) >= QTD:
                break
            if o.get("plataforma", "shopee") != "shopee" or not cabe(o):
                continue
            o = dict(o)
            if precos.conferir(o) in ("sumiu", "subiu"):
                continue
            try:
                foto = _baixar_foto(o["imagem"])
            except Exception:
                continue
            itens.append({"oferta": o, "pedido": o.get("palavra") or "", "vezes": n, "foto": foto, "origem": "eu_quero"})
            ids.add(o["id"])
            print(f"💚 Plano B: {o['nome'][:60]} ({n} pedidos de link)")
    return itens, rotulo


# ---------------------------------------------------------------- arte
def _ctext(d, y, t, f, fill, stroke=0, sf=(0, 0, 0)):
    w = d.textlength(t, font=f)
    d.text(((W - w) / 2, y), t, font=f, fill=fill, stroke_width=stroke, stroke_fill=sf)


def _quebrar(d, t, f, largura, maximo=2):
    linhas, atual = [], []
    for p in t.split():
        if d.textlength(" ".join(atual + [p]), font=f) > largura and atual:
            linhas.append(" ".join(atual))
            atual = [p]
        else:
            atual.append(p)
    linhas.append(" ".join(atual))
    if len(linhas) > maximo:
        linhas = linhas[:maximo]
        while d.textlength(linhas[-1] + "…", font=f) > largura and " " in linhas[-1]:
            linhas[-1] = linhas[-1].rsplit(" ", 1)[0]
        linhas[-1] += "…"
    return linhas


def _cena(tipo):
    """A arte do Zé (4:3) encaixada no 4:5, com o fundo feito da própria cena desfocada."""
    tm = TEMAS[tipo]
    src = Image.open(CAPAS / f"{tipo}.jpg").convert("RGB")
    img = src.resize((W, int(src.height * W / src.width)), Image.LANCZOS)
    ih = img.height
    bg = src.resize((W, H)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), tm["mistura"]), tm["forca"])
    m = Image.new("L", (W, ih), 255)
    md = ImageDraw.Draw(m)
    for y in range(70):
        a = int(255 * y / 70)
        md.line((0, y, W, y), fill=a)
        md.line((0, ih - 1 - y, W, ih - 1 - y), fill=a)
    return bg, img, m, ih


def capa(tipo, rotulo, n=QTD):
    tm = TEMAS[tipo]
    bg, img, m, ih = _cena(tipo)
    top = 270
    bg.paste(img, (0, top), m)
    d = ImageDraw.Draw(bg)
    es = tm["borda"]
    t = f"{config.NOME_MARCA.upper()}  •  {rotulo}"
    f = _f(30)
    w = d.textlength(t, font=f)
    d.rounded_rectangle(((W - w) / 2 - 24, 28, (W + w) / 2 + 24, 78), 25, fill=es)
    _ctext(d, 34, t, f, AM)
    _ctext(d, 82, f"TOP {n} DA SEMANA" if tipo == "semana" else f"TOP {n} DO MÊS", _f(96), AM, 6, es)
    _ctext(d, 196, "o que vocês mais pediram pro Zé" if tipo == "semana" else "o que mais saiu da mina esse mês",
           _f(44), BR, 4, es)
    yb = top + ih - 60
    _ctext(d, yb + 60, "Arrasta pro lado e vê o que ele achou" if tipo == "semana"
           else "Arrasta pro lado e vê os campeões", _f(44), BR, 4, es)
    t = "Não achou o seu? Comenta aqui que o Zé garimpa!"
    f = _f(32)
    w = d.textlength(t, font=f)
    d.rounded_rectangle(((W - w) / 2 - 28, yb + 142, (W + w) / 2 + 28, yb + 204), 31, fill=AM)
    _ctext(d, yb + 150, t, f, es)
    return bg


def slide_produto(tipo, pos, item):
    tm = TEMAS[tipo]
    o = item["oferta"]
    im = Image.new("RGB", (W, H), tm["fundo"])
    d = ImageDraw.Draw(im)
    d.ellipse((50, 40, 190, 180), fill=AM)
    f = _f(96)
    d.text((120 - d.textlength(str(pos), font=f) / 2, 38), str(pos), font=f, fill=tm["borda"])
    if item["origem"] == "busca":
        d.text((220, 58), "VOCÊS PEDIRAM:", font=_f(32), fill=AM)
        d.text((220, 98), _quebrar(d, item["pedido"].capitalize(), _f(52), W - 270, 1)[0], font=_f(52), fill=BR)
    else:
        d.text((220, 58), "VOCÊS QUISERAM:", font=_f(32), fill=AM)
        d.text((220, 98), "Campeão de pedidos", font=_f(52), fill=BR)
    # foto do produto, inteira dentro do cartão
    d.rounded_rectangle((60, 220, W - 60, 900), 36, fill=CARD)
    foto = item["foto"].copy()
    foto.thumbnail((W - 180, 620), Image.LANCZOS)
    im.paste(foto, ((W - foto.width) // 2, 250 + (620 - foto.height) // 2))
    unid = "na semana" if tipo == "semana" else "no mês"
    t = (f"pedido {item['vezes']}x {unid}" if item["origem"] == "busca" and item["vezes"] > 1
         else "pedido pelos seguidores" if item["origem"] == "busca" else f"{item['vezes']} pediram o link")
    f = _f(30)
    w = d.textlength(t, font=f)
    d.rounded_rectangle((W - 90 - w - 40, 250, W - 90, 306), 28, fill=VERMELHO)
    d.text((W - 90 - w - 20, 256), t, font=f, fill=BR)
    y = 930
    for ln in _quebrar(d, o["nome"], _f(40), W - 140):
        _ctext(d, y, ln, _f(40), BR)
        y += 52
    variacoes = o.get("preco_max") and o["preco_max"] > o["preco"] * 1.02
    _ctext(d, y + 12, "a partir de" if variacoes else "por", _f(30), BEGE)
    _ctext(d, y + 44, f"R$ {o['preco_fmt']}", _f(80), AM, 4, tm["borda"])
    vendas = f"{o.get('vendas', 0):,}".replace(",", ".")
    _ctext(d, y + 150, f"nota {str(o.get('nota', '')).replace('.', ',')}   •   {vendas}+ vendidos", _f(32), BR)
    t = f"Comenta  QUERO {pos}  que o Zé te manda o link"
    f = _f(34)
    w = d.textlength(t, font=f)
    d.rounded_rectangle(((W - w) / 2 - 30, H - 112, (W + w) / 2 + 30, H - 44), 34, fill=VERDE)
    _ctext(d, H - 104, t, f, BR)
    return im


def slide_final(tipo):
    tm = TEMAS[tipo]
    bg, img, m, ih = _cena(tipo)
    im = Image.new("RGB", (W, H), tm["fundo"])
    im.paste(bg.crop((0, 0, W, H)), (0, 0))
    im.paste(img, (0, 0), m)
    d = ImageDraw.Draw(im)
    es = tm["borda"]
    _ctext(d, 830, "Não achou o que procura?", _f(62), AM, 5, es)
    for i, ln in enumerate(["Comenta aqui o que você quer", "que o Zé garimpa pra você", "e manda no seu direct"]):
        _ctext(d, 930 + i * 58, ln, _f(44), BR, 3, es)
    t = f"Segue o @{config.USUARIO_IG if hasattr(config, 'USUARIO_IG') else 'garimpovip4'} pra não perder o próximo Top 5"
    f = _f(30)
    w = d.textlength(t, font=f)
    d.rounded_rectangle(((W - w) / 2 - 30, H - 130, (W + w) / 2 + 30, H - 62), 34, fill=AM)
    _ctext(d, H - 121, t, f, es)
    return im


def gerar(tipo, pasta):
    itens, rotulo = escolher(tipo)
    if len(itens) < 3:
        print(f"⚠️  Só {len(itens)} produtos para o Top — não vale postar carrossel tão curto.")
        return None
    pasta.mkdir(parents=True, exist_ok=True)
    marca = int(time.time())
    arqs = []
    imagens = [capa(tipo, rotulo, len(itens))] + [slide_produto(tipo, i, it) for i, it in enumerate(itens, 1)] + [slide_final(tipo)]
    for i, im in enumerate(imagens, 1):
        nome = f"top-{tipo}-{marca}-{i}.jpg"
        im.save(pasta / nome, quality=92)
        arqs.append(nome)
    return {"tipo": tipo, "rotulo": rotulo, "arquivos": arqs,
            "itens": [{k: it["oferta"].get(k) for k in ("id", "nome", "preco_fmt", "link_afiliado", "plataforma")}
                      | {"pedido": it["pedido"], "vezes": it["vezes"], "origem": it["origem"]} for it in itens]}


def _curto(nome, n=55):
    nome = " ".join(nome.split())
    return nome if len(nome) <= n else nome[:n].rsplit(" ", 1)[0] + "…"


def legenda(info):
    num = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    titulo = (f"🏆 TOP {len(info['itens'])} DA SEMANA — o que vocês mais pediram pro Zé!" if info["tipo"] == "semana"
              else f"🏆 TOP {len(info['itens'])} DO MÊS — os campeões de {info['rotulo'].split(' de ')[0]}!")
    linhas = [titulo, ""]
    for i, it in enumerate(info["itens"]):
        linhas.append(f"{num[i]} {_curto(it['nome'])} — R$ {it['preco_fmt']}")
    linhas += ["", "👇 Comenta QUERO + o número (ex.: QUERO 3) que o Zé te manda o link no direct!",
               "🔎 Não achou o seu? Comenta o que você procura que o Zé garimpa pra você 🤠",
               "", "Preços conferidos na hora do post — podem mudar na Shopee.",
               "", "#garimpovip #achadinhos #achadosshopee #ofertas #promocao #top5"]
    return "\n".join(linhas)


# ---------------------------------------------------------------- publicar
def tipo_de_hoje(hoje=None):
    hoje = hoje or agora()
    if (hoje + timedelta(days=1)).day == 1:
        return "mes"          # último dia do mês (se cair numa sexta, o mensal substitui o semanal)
    if hoje.weekday() == 4:
        return "semana"
    return None


def _saida(chave, valor):
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"{chave}={valor}\n")


def preparar(tipo="auto"):
    _saida("tem_post", "false")
    tipo = tipo_de_hoje() if tipo == "auto" else tipo
    if not tipo:
        print("Hoje não é dia de Top (só sextas e no último dia do mês).")
        return
    if not instagram.tem_token():
        print("⏸️  IG_ACCESS_TOKEN ainda não configurado.")
        return
    pasta = PASTA_SITE / "midia" / "top"
    (PASTA_SITE / ".nojekyll").parent.mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    for fixo in (config.RAIZ / "assets" / "paginas").glob("*.html"):
        (PASTA_SITE / fixo.name).write_text(fixo.read_text(encoding="utf-8"), encoding="utf-8")
    info = gerar(tipo, pasta)
    if not info:
        return
    video = CAPAS / f"{tipo}.mp4"
    if video.exists():
        try:
            nome = f"top-story-{int(time.time())}.mp4"
            story_do_ze(video, pasta / nome, tipo)
            info["story"] = nome
        except Exception as e:
            print(f"::warning::Story do Top não saiu ({e}); o carrossel sai mesmo assim.")
    ARQ_PROXIMO.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    _saida("tem_post", "true")
    print(f"🏆 Top ({tipo}) preparado com {len(info['itens'])} produtos.")


def story_do_ze(video, saida, tipo):
    """Vídeo do Zé (9:16) com a chamada escrita por cima: avisa no story que saiu o Top."""
    import subprocess
    from .ze import _ffmpeg
    png = saida.with_suffix(".png")
    cam = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    d.rectangle((0, 1560, 1080, 1920), fill=(0, 0, 0, 120))
    es = TEMAS[tipo]["borda"]
    _ctext(d, 1610, "SAIU O TOP 5 DA SEMANA!" if tipo == "semana" else "SAIU O TOP 5 DO MÊS!", _f(66), AM, 5, es)
    _ctext(d, 1720, "Corre no perfil e confere", _f(46), BR, 4, es)
    cam.save(png)
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(video), "-i", str(png), "-filter_complex",
                    "[0:v]scale=1080:1920,setsar=1[v];[v][1:v]overlay=0:0", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-movflags", "+faststart", str(saida)], check=True)
    png.unlink(missing_ok=True)


def carregar():
    if ARQ_TOP.exists():
        return json.loads(ARQ_TOP.read_text(encoding="utf-8"))
    return {"posts": {}}


def publicar():
    from .postar import _esperar_url
    info = json.loads(ARQ_PROXIMO.read_text(encoding="utf-8"))
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PAGES_URL ausente.")
    urls = [f"{base}/midia/top/{a}" for a in info["arquivos"]]
    for u in urls:
        _esperar_url(u)
    ig_id = instagram.conferir_conta()["user_id"]
    filhos = []
    for u in urls:
        filhos.append(instagram.criar_item_carrossel(ig_id, u))
    for c in filhos:
        instagram.aguardar_container(c)
    cont = instagram.criar_carrossel(ig_id, filhos, legenda(info))
    instagram.aguardar_container(cont)
    media_id = instagram.publicar(ig_id, cont)
    dados = carregar()
    dados["posts"][media_id] = {"tipo": info["tipo"], "rotulo": info["rotulo"], "itens": info["itens"],
                                "postado_em": agora().strftime(FMT), "permalink": instagram.permalink(media_id)}
    limite = (agora() - timedelta(days=60)).strftime(FMT)   # links só valem enquanto o post está ativo
    dados["posts"] = {k: v for k, v in dados["posts"].items() if v.get("postado_em", "") >= limite}
    ARQ_TOP.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    ARQ_PROXIMO.unlink(missing_ok=True)
    print(f"✅ Top ({info['tipo']}) publicado: {dados['posts'][media_id]['permalink'] or media_id}")
    if info.get("story"):
        try:
            surl = f"{base}/midia/top/{info['story']}"
            _esperar_url(surl)
            cs = instagram.criar_story(ig_id, video_url=surl)
            instagram.aguardar_container(cs)
            instagram.publicar(ig_id, cs)
            print("📲 Story do Zé avisando do Top publicado.")
        except Exception as e:
            print(f"::warning::Story do Top falhou: {e}")


def previa(tipo="semana"):
    pasta = config.RAIZ / "data" / "relatorios" / "top"
    shutil.rmtree(pasta, ignore_errors=True)
    info = gerar(tipo, pasta)
    if info:
        (pasta / "legenda.txt").write_text(legenda(info), encoding="utf-8")
        if (CAPAS / f"{tipo}.mp4").exists():
            try:
                story_do_ze(CAPAS / f"{tipo}.mp4", pasta / "story.mp4", tipo)
            except Exception as e:
                print(f"::warning::Story da prévia falhou: {e}")
        print(legenda(info))


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "preparar"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        if acao == "preparar":
            preparar(arg or "auto")
        elif acao == "publicar":
            publicar()
        elif acao == "previa":
            previa(arg or "semana")
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
