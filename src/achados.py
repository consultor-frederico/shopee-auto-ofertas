"""🛍️ Carrossel de Achados — vários produtos num post só, sempre abrindo com um vídeo do Zé (Garimpo VIP)
ou da Ana (Ana Novo Achados).

Slides (1080x1350): 1) vídeo deles com o título por cima → 2) a 5) produtos numerados (a mesma arte do
feed de cada conta, com o número) → último) chamada para comentar e seguir.
Quem comenta "QUERO 2" recebe o link do 2º; só "QUERO" recebe a lista com todos (ver responder.responder_top,
que lê o registro em data/<perfil>/top.json).

Uso:
  python -m src.achados preparar   → escolhe os produtos e gera os slides em site/midia/achados/
  python -m src.achados publicar   → publica o carrossel (precisa do PAGES_URL) e marca as ofertas como postadas
  python -m src.achados previa     → só gera os slides em data/relatorios/achados/ (não posta, não confere preço)
"""
import json
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import timedelta

from PIL import Image, ImageDraw

from . import achados_artes as artes, config, imagem, instagram
from .garimpar import FMT, agora, carregar_fila, salvar_fila

ANA = config.PERFIL == "ana"
QTD = max(3, min(5, int(os.getenv("ACHADOS_QTD", "4") or 4)))
MINIMO = max(2, int(os.getenv("ACHADOS_MINIMO", "3") or 3))
L, A = 1080, 1350
PASTA_SITE = config.RAIZ / "site"
ARQ_PROXIMO = config.PASTA_PERFIL / "achados_proximo.json"
ARQ_ESTADO = config.PASTA_PERFIL / "achados.json"
ARQ_TOP = config.PASTA_PERFIL / "top.json"   # o responder lê daqui (mesmo formato do Top 5)
NUM = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


def _saida(chave, valor):
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"{chave}={valor}\n")


# ---------------------------------------------------------------- o que entra
def escolher(fila, conferir=True):
    """QTD ofertas de tipos diferentes (nada de dois espelhos no mesmo carrossel), com foto e preço conferidos.
    Primeiro tenta uma de cada categoria; se faltar, completa com a mesma categoria."""
    from . import postar, precos, variedade
    lista = [o for o in postar.candidatos_ordenados(fila) if not o.get("video_manual") and not o.get("pedido")]
    itens, familias, categorias, ids = [], set(), set(), set()
    shark = False

    def tentar(o, so_categoria_nova):
        nonlocal shark
        fam = variedade.familia(o)
        if o["id"] in ids or fam in familias or (o.get("plataforma") == "sharkninja" and shark):
            return
        if so_categoria_nova and o.get("categoria") in categorias:
            return
        if conferir:
            situacao = precos.conferir(o)
            if situacao in ("sumiu", "subiu"):
                o["status"] = "descartado"
                o["motivo"] = "produto fora do ar" if situacao == "sumiu" else "preço subiu desde o garimpo"
                print(f"🗑️  {o.get('titulo')}: {o['motivo']} — pulando.")
                ids.add(o["id"])
                return
        try:
            foto = imagem._baixar_foto(o["imagem"])
        except Exception as e:
            print(f"⚠️  Foto de {o['id']} não baixou ({e}); tentando outra oferta.")
            ids.add(o["id"])
            return
        itens.append({"oferta": o, "foto": foto})
        ids.add(o["id"])
        familias.add(fam)
        categorias.add(o.get("categoria"))
        shark = shark or o.get("plataforma") == "sharkninja"
        print(f"🛍️  {len(itens)}. {o['titulo'][:60]} — R$ {o['preco_fmt']} ({o.get('categoria')})")

    for so_categoria_nova in (True, False):
        for o in lista:
            if len(itens) >= QTD:
                break
            tentar(o, so_categoria_nova)
    return itens


# ---------------------------------------------------------------- slides dos produtos
def slide_produto(oferta, foto, pos, destino, v=0):
    """Arte do produto no estilo `v` (0 = a do feed da conta; 1 e 2 = versões diferentes), com o número para "QUERO 2"."""
    (artes.produto_ana if ANA else artes.produto_garimpo)(v % artes.N_PRODUTO, oferta, foto, pos, destino)


# ---------------------------------------------------------------- slide final
def slide_final(n, v):
    return artes.final_ana(v, n) if ANA else artes.final_garimpo(v, n, v)


# ---------------------------------------------------------------- vídeo de abertura
def _carregar_estado():
    if ARQ_ESTADO.exists():
        return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
    return {"videos": {}, "n": 0}


def variante():
    """Número do carrossel (cada um usa uma versão diferente das artes). ACHADOS_VARIANTE força uma, p/ prévias."""
    forcada = os.getenv("ACHADOS_VARIANTE")
    if forcada not in (None, ""):
        return int(forcada)
    return int(_carregar_estado().get("n", 0))

def escolher_video():
    """Vídeo do Zé (ou da Ana) da vez: primeiro os que nunca abriram um carrossel, depois o mais antigo."""
    from . import ze
    lista = [v for v in ze.videos() if "busca" not in v.name]
    if not lista:
        raise RuntimeError(f"sem vídeos {ze.PREFIXO}*.mp4 em {ze.PASTA}")
    usados = _carregar_estado()["videos"]
    novos = [v for v in lista if v.name not in usados]
    if novos:
        return random.choice(novos)
    return min(lista, key=lambda v: usados[v.name])


def gerar_video_abertura(destino, v=0):
    """O vídeo deles em 4:5, com o título por cima e música baixinha (some quando falam). Devolve o nome do clipe."""
    from . import ze
    clipe = escolher_video()
    faixa = str(destino)[: -len(".mp4")] + "-faixa.png"
    bruto = str(destino)[: -len(".mp4")] + "-bruto.mp4"
    from .ze import dias_para_black_friday
    artes.faixa_titulo(faixa, v, dias_para_black_friday())
    dur = max(4.0, ze._duracao(clipe))
    filtro = (f"[0:v]scale={L}:{A}:force_original_aspect_ratio=increase,crop={L}:{A}:(iw-{L})/2:(ih-{A})*0.25,"
              f"setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={dur:.2f}[b];[b][1:v]overlay=0:0,format=yuv420p[v];"
              "[0:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]")
    subprocess.run([ze._ffmpeg(), "-y", "-loglevel", "error", "-i", str(clipe), "-i", faixa,
                    "-filter_complex", filtro, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", bruto], check=True)
    os.remove(faixa)
    try:
        musicas = ze.escolher_musicas({"id": clipe.name}, dur) if ze.MUSICA_LIGADA else []
        if musicas:
            ze._com_musica(bruto, musicas, str(destino))
            os.remove(bruto)
    except Exception as e:
        print(f"::warning::Música do vídeo de abertura não entrou ({e}).")
    if os.path.exists(bruto):
        os.replace(bruto, destino)
    print(f"{'💚 Ana' if ANA else '🤠 Zé'} abre o carrossel: {clipe.name}")
    return clipe.name


def gerar_story(clipe, destino):
    """Story 9:16 com o mesmo vídeo deles e o aviso "carrossel novo no perfil" (story é onde a Ana mais aparece)."""
    from . import ze
    png = str(destino)[: -len(".mp4")] + ".png"
    cam = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    if ANA:
        from . import layout_ana as la
        f1, f2 = la.serif(80), la.sans(44, "SemiBold")
        d.rounded_rectangle((60, 1500, 1020, 1800), 50, fill=(255, 248, 244, 230))
        cor1, cor2 = la.TEXTO, la.ROSA_ESCURA
        t1, t2 = "achadinhos novos!", "corre no perfil e confere"
    else:
        f1, f2 = imagem._fonte(76, "Black"), imagem._fonte(44, "SemiBold")
        d.rounded_rectangle((60, 1500, 1020, 1800), 50, fill=(45, 28, 12, 225))
        cor1, cor2 = imagem.DOURADO_CLARO, imagem.BRANCO
        t1, t2 = "ACHADOS NOVOS!", "corre no perfil e confere"
    d.text(((1080 - d.textlength(t1, font=f1)) / 2, 1560), t1, font=f1, fill=cor1)
    d.text(((1080 - d.textlength(t2, font=f2)) / 2, 1690), t2, font=f2, fill=cor2)
    cam.save(png)
    filtro = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[v];"
              "[v][1:v]overlay=0:0,format=yuv420p[o]")
    subprocess.run([ze._ffmpeg(), "-y", "-loglevel", "error", "-i", str(ze.PASTA / clipe), "-i", png,
                    "-filter_complex", filtro, "-map", "[o]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "21", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(destino)], check=True)
    os.remove(png)


# ---------------------------------------------------------------- legenda
def legenda(itens):
    from .ze import HASHTAGS, HASHTAGS_ANA, dias_para_black_friday
    n = len(itens)
    if ANA:
        linhas = [f"💚 {n} achadinhos que eu separei pra você hoje!", ""]
    else:
        linhas = [f"🤠 O Zé garimpou {n} achados pra você hoje! ⛏️", ""]
    for i, it in enumerate(itens):
        o = it["oferta"]
        linhas.append(f"{NUM[i]} {_curto(o['titulo'])} — R$ {o['preco_fmt']}")
    if ANA:
        linhas += ["", "👇 Comenta QUERO + o número (ex.: QUERO 2) que eu te mando o link no direct! 💚",
                   "💬 Quer outra coisa? Comenta o que você procura que eu busco pra você."]
    else:
        linhas += ["", "👇 Comenta QUERO + o número (ex.: QUERO 2) que o Zé te manda o link no direct!",
                   "🔎 Não achou o seu? Comenta o que você procura que o Zé garimpa pra você 🤠"]
    dias = dias_para_black_friday()
    if 0 < dias <= 45:
        linhas.append(f"⏳ Faltam {dias} dias pra Black Friday! " + ("Me segue pra ver tudo primeiro 💚" if ANA
                                                                    else "Segue o Zé pra ver tudo primeiro!"))
    linhas += ["", "Preços conferidos na hora do post — podem mudar na loja. Links de afiliado: você paga o mesmo.",
               "", HASHTAGS_ANA if ANA else HASHTAGS]
    return "\n".join(linhas)


def _curto(nome, n=55):
    nome = " ".join(str(nome).split())
    return nome if len(nome) <= n else nome[:n].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------- preparar / publicar
def gerar(itens, pasta):
    v = variante()
    pasta.mkdir(parents=True, exist_ok=True)
    marca = int(time.time())
    arqs = []
    nome = f"achados-{marca}-1.mp4"
    clipe = gerar_video_abertura(pasta / nome, v)
    arqs.append(nome)
    for i, it in enumerate(itens, 2):
        nome = f"achados-{marca}-{i}.jpg"
        slide_produto(it["oferta"], it["foto"], i - 1, pasta / nome, v)
        arqs.append(nome)
    nome = f"achados-{marca}-{len(itens) + 2}.jpg"
    slide_final(len(itens), v).save(pasta / nome, quality=92)
    arqs.append(nome)
    story = None
    try:
        story = f"achados-{marca}-story.mp4"
        gerar_story(clipe, pasta / story)
    except Exception as e:
        print(f"::warning::Story do carrossel não saiu ({e}); o carrossel sai mesmo assim.")
        story = None
    return {"arquivos": arqs, "clipe": clipe, "story": story,
            "itens": [{k: it["oferta"].get(k) for k in ("id", "nome", "titulo", "preco_fmt", "link_afiliado", "plataforma")}
                      for it in itens]}


def preparar():
    _saida("tem_post", "false")
    if not instagram.tem_token():
        print("⏸️  Token do Instagram ausente — carrossel em espera.")
        return
    fila = carregar_fila()
    itens = escolher(fila)
    salvar_fila(fila)   # guarda o que foi descartado na conferência de preço
    if len(itens) < MINIMO:
        print(f"⚠️  Só {len(itens)} produtos bons na fila — não vale postar carrossel tão curto.")
        return
    pasta = PASTA_SITE / "midia" / "achados"
    (PASTA_SITE).mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    for fixo in (config.RAIZ / "assets" / "paginas").glob("*.html"):
        (PASTA_SITE / fixo.name).write_text(fixo.read_text(encoding="utf-8"), encoding="utf-8")
    info = gerar(itens, pasta)
    info["legenda"] = legenda(itens)
    ARQ_PROXIMO.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    _saida("tem_post", "true")
    print(f"🛍️  Carrossel de achados preparado com {len(itens)} produtos.")


def publicar():
    from .postar import _esperar_url
    info = json.loads(ARQ_PROXIMO.read_text(encoding="utf-8"))
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PAGES_URL ausente.")
    urls = [f"{base}/midia/achados/{a}" for a in info["arquivos"]]
    for u in urls:
        _esperar_url(u)
    ig_id = instagram.conferir_conta()["user_id"]
    filhos = [instagram.criar_item_carrossel(ig_id, video_url=u) if u.endswith(".mp4")
              else instagram.criar_item_carrossel(ig_id, imagem_url=u) for u in urls]
    for c in filhos:
        instagram.aguardar_container(c)
    cont = instagram.criar_carrossel(ig_id, filhos, info["legenda"])
    instagram.aguardar_container(cont)
    media_id = instagram.publicar(ig_id, cont)
    permalink = instagram.permalink(media_id)
    agora_s = agora().strftime(FMT)
    # registro que o responder lê ("QUERO 2" → link do 2º; só "QUERO" → lista com todos)
    dados = json.loads(ARQ_TOP.read_text(encoding="utf-8")) if ARQ_TOP.exists() else {"posts": {}}
    dados["posts"][media_id] = {"tipo": "achados", "rotulo": agora().strftime("%d/%m"), "itens": info["itens"],
                                "postado_em": agora_s, "permalink": permalink}
    limite = (agora() - timedelta(days=60)).strftime(FMT)
    dados["posts"] = {k: v for k, v in dados["posts"].items() if v.get("postado_em", "") >= limite}
    ARQ_TOP.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    # as ofertas saem da fila de pendentes (sem id_post: quem responde por elas é o registro acima)
    fila = carregar_fila()
    for it in info["itens"]:
        o = fila["ofertas"].get(it["id"])
        if o:
            o.update({"status": "postado", "formato": "achados", "postado_em": agora_s,
                      "postado_ts": time.time(), "achados_post": media_id, "permalink": permalink})
    salvar_fila(fila)
    estado = _carregar_estado()
    estado["videos"][info["clipe"]] = agora_s
    estado["n"] = int(estado.get("n", 0)) + 1
    ARQ_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    ARQ_PROXIMO.unlink(missing_ok=True)
    print(f"✅ Carrossel de achados publicado ({config.ARROBA}): {permalink or media_id}")
    if info.get("story"):
        try:
            surl = f"{base}/midia/achados/{info['story']}"
            _esperar_url(surl)
            cs = instagram.criar_story(ig_id, video_url=surl)
            instagram.aguardar_container(cs)
            instagram.publicar(ig_id, cs)
            print("📲 Story avisando do carrossel publicado.")
        except Exception as e:
            print(f"::warning::Story do carrossel falhou: {e}")


def previa():
    fila = carregar_fila()
    itens = escolher(fila, conferir=False)
    if len(itens) < MINIMO:
        print(f"⚠️  Só {len(itens)} produtos na fila.")
        return
    pasta = config.RAIZ / "data" / "relatorios" / "achados"
    shutil.rmtree(pasta, ignore_errors=True)
    info = gerar(itens, pasta)
    (pasta / "legenda.txt").write_text(legenda(itens), encoding="utf-8")
    print(legenda(itens))
    print("Arquivos:", ", ".join(info["arquivos"]))


if __name__ == "__main__":
    acao = {"preparar": preparar, "publicar": publicar, "previa": previa}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if not acao:
        print("Uso: python -m src.achados preparar|publicar|previa")
        sys.exit(2)
    try:
        acao()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
