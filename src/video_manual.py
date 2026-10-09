"""Vídeos enviados manualmente para a pasta videos/.

Como usar (no GitHub, pelo navegador):
  1. Suba o vídeo .mp4 em videos/ (Add file → Upload files).
  2. Em videos/lista.txt, adicione uma linha:  nome-do-arquivo.mp4 | link do produto na Shopee
     (alternativa: nomeie o arquivo com o ID do produto, ex.: 58254505951.mp4)

O robô busca a oferta com o seu link de afiliado, gera a legenda, monta o Reels com o vídeo
e publica no próximo horário, com prioridade. Depois de publicado, o vídeo sai da pasta.
"""
import re
import shutil
import subprocess

import requests
from PIL import Image, ImageDraw, ImageOps

from . import config, legenda, shopee
from .garimpar import FMT, agora, normalizar
from .imagem import (BRANCO, CINZA, DOURADO, DOURADO_CLARO, ESCURO, LARANJA,
                     _brl, _estrela, _fonte, _quebrar, selo_loja)

PASTA = config.RAIZ / "videos"
LISTA = PASTA / "lista.txt"
DURACAO_MAX = 90          # segundos
PRIORIDADE = 1000         # pontos: passa na frente das ofertas garimpadas
L, A = 1080, 1920
from .imagem import FUNDO  # noqa: E402
TOPO, BASE = 250, 1360    # faixa do vídeo: entre o logo e o painel de preço

PADROES_ID = [r"-i\.\d+\.(\d+)", r"/product/\d+/(\d+)", r"/opaanlp/\d+/(\d+)", r"[?&]itemid=(\d+)"]


def extrair_item_id(link: str):
    link = link.strip()
    if re.fullmatch(r"\d{6,}", link):
        return link
    if "s.shopee" in link or "shp.ee" in link:
        try:
            link = requests.get(link, timeout=20, allow_redirects=True,
                                headers={"User-Agent": "Mozilla/5.0"}).url
        except requests.RequestException as e:
            print(f"⚠️  Não consegui abrir o link curto {link}: {e}")
            return None
    for p in PADROES_ID:
        m = re.search(p, link, re.I)
        if m:
            return m.group(1)
    return None


def _linhas_lista():
    if not LISTA.exists():
        return []
    itens = []
    for linha in LISTA.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.strip().startswith("#") or "|" not in linha:
            continue
        arq, link = [x.strip() for x in linha.split("|", 1)]
        itens.append((arq, link, linha))
    return itens


def pendentes():
    """[(caminho_do_video, item_id, linha_da_lista_ou_None)]"""
    if not PASTA.exists():
        return []
    achados, usados = [], set()
    for arq, link, linha in _linhas_lista():
        caminho = PASTA / arq
        usados.add(arq)
        if not caminho.exists():
            print(f"⚠️  videos/lista.txt cita '{arq}', mas o arquivo não está na pasta.")
            continue
        item = extrair_item_id(link)
        if not item:
            print(f"::warning::Não reconheci o produto do link '{link}' (vídeo {arq}).")
            continue
        achados.append((caminho, item, linha))
    for caminho in PASTA.glob("*.mp4"):
        if caminho.name not in usados and re.fullmatch(r"\d{6,}", caminho.stem):
            achados.append((caminho, caminho.stem, None))
    return achados


def registrar_na_fila(fila):
    """Coloca na fila (com prioridade) cada oferta que tem vídeo manual esperando."""
    for caminho, item, linha in pendentes():
        rel = str(caminho.relative_to(config.RAIZ))
        reg = fila["ofertas"].get(item)
        if reg and reg.get("video_manual") == rel and reg.get("status") == "pendente":
            continue
        if reg and reg.get("video_manual") == rel and reg.get("status") == "erro":
            print(f"::warning::O vídeo {caminho.name} falhou 2 vezes ({reg.get('ultimo_erro', '')[:120]}). "
                  "Troque o arquivo ou remova-o da pasta.")
            continue
        try:
            nos = shopee.buscar_por_item(item)
        except Exception as e:
            print(f"::warning::Shopee falhou ao buscar o produto {item}: {e}")
            continue
        if not nos:
            print(f"::warning::O produto {item} (vídeo {caminho.name}) não está no programa de afiliados.")
            continue
        o = normalizar(nos[0], (reg or {}).get("categoria", "manual"), "vídeo manual")
        texto = legenda.gerar(o)
        o.update({"titulo": texto["titulo"], "legenda": texto["legenda"], "status": "pendente",
                  "criado_em": agora().strftime(FMT), "postado_em": "", "id_post": "",
                  "pontos": PRIORIDADE, "video_manual": rel, "linha_lista": linha or ""})
        fila["ofertas"][item] = o
        print(f"🎥 Vídeo manual na fila: {o['titulo']} (R$ {o['preco_fmt']}) ← {caminho.name}")


def baixar_da_pasta(oferta):
    """Remove o vídeo e a linha da lista depois de publicado."""
    rel = oferta.get("video_manual")
    if rel:
        (config.RAIZ / rel).unlink(missing_ok=True)
    linha = oferta.get("linha_lista")
    if linha and LISTA.exists():
        linhas = LISTA.read_text(encoding="utf-8").splitlines()
        LISTA.write_text("\n".join(x for x in linhas if x != linha) + "\n", encoding="utf-8")
    oferta["video_manual_usado"] = rel
    oferta.pop("video_manual", None)


def _moldura(oferta):
    """PNG transparente no meio: logo em cima, painel de preço e chamada embaixo."""
    img = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, L, TOPO], fill=FUNDO)
    try:
        logo = Image.open(config.LOGO).convert("RGBA")
        logo = ImageOps.contain(logo, (320, 200), Image.LANCZOS)
        img.alpha_composite(logo, ((L - logo.width) // 2, 28))
    except Exception:
        pass
    d.rectangle([0, BASE, L, A], fill=FUNDO)
    selo_loja(d, oferta, 40, TOPO + 24, escala=1.1)
    y = BASE + 40
    f_tit = _fonte(58, "ExtraBold")
    for linha in _quebrar(d, oferta["titulo"], f_tit, L - 140, max_linhas=1):
        d.text((70, y), linha, font=f_tit, fill=ESCURO)
    y += 90
    x = 70
    f_de, f_rs, f_preco = _fonte(42, "Medium"), _fonte(54, "Bold"), _fonte(130, "Black")
    if oferta.get("preco_de"):
        de = f"R$ {_brl(oferta['preco_de'])}"
        d.text((x, y + 50), de, font=f_de, fill=CINZA)
        w = d.textlength(de, font=f_de)
        d.line([x - 4, y + 77, x + w + 4, y + 77], fill=CINZA, width=5)
        x += w + 30
    d.text((x, y + 44), "R$", font=f_rs, fill=DOURADO)
    x += d.textlength("R$", font=f_rs) + 12
    d.text((x, y - 20), oferta["preco_fmt"], font=f_preco, fill=LARANJA)
    if oferta.get("desconto"):
        sx, sy, r = L - 150, BASE - 40, 110
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=DOURADO, outline=BRANCO, width=8)
        f1, f2 = _fonte(68, "Black"), _fonte(36, "Bold")
        t1 = f"-{oferta['desconto']}%"
        d.text((sx - d.textlength(t1, font=f1) / 2, sy - 58), t1, font=f1, fill=BRANCO)
        d.text((sx - d.textlength("OFF", font=f2) / 2, sy + 20), "OFF", font=f2, fill=BRANCO)
    yi = y + 160
    _estrela(d, 92, yi + 25, 24, DOURADO)
    nota = (f"{oferta['avaliacao_pct']:.0f}% aprovação" if oferta.get("avaliacao_pct")
                else f"{oferta['nota']:.1f}".replace(".", ","))
    vendas = f"{oferta['vendas']:,}".replace(",", ".")
    d.text((124, yi), f"{nota}   •   {vendas}+ vendidos", font=_fonte(40, "SemiBold"), fill=CINZA)
    d.rectangle([0, A - 170, L, A], fill=ESCURO)
    f_cta = _fonte(52, "ExtraBold")
    partes = [("COMENTE ", BRANCO), ("EU QUERO", DOURADO_CLARO)]
    x = (L - sum(d.textlength(p, font=f_cta) for p, _ in partes)) / 2
    for p, cor in partes:
        d.text((x, A - 140), p, font=f_cta, fill=cor)
        x += d.textlength(p, font=f_cta)
    f2 = _fonte(36, "SemiBold")
    sub = "que eu te mando o link no direct"
    d.text(((L - d.textlength(sub, font=f2)) / 2, A - 70), sub, font=f2, fill="#CFC6B8")
    return img


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _tem_audio(ffmpeg, video):
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(video)], capture_output=True, text=True)
    return "Audio:" in r.stderr


def gerar_reels(oferta, video, destino):
    ffmpeg = _ffmpeg()
    moldura = destino.with_suffix(".moldura.png")
    _moldura(oferta).save(moldura)
    altura = BASE - TOPO
    filtro = (f"color=c={FUNDO}:s={L}x{A}:r=30[bg];"
              f"[0:v]scale={L}:{altura}:force_original_aspect_ratio=decrease,setsar=1[v];"
              f"[bg][v]overlay=(W-w)/2:{TOPO}+({altura}-h)/2:shortest=1[b];"
              f"[b][1:v]overlay=0:0,format=yuv420p[out]")
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(video), "-loop", "1", "-i", str(moldura)]
    if _tem_audio(ffmpeg, video):
        audio = ["-map", "0:a:0"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        audio = ["-map", "2:a"]
    cmd += ["-filter_complex", filtro, "-map", "[out]", *audio, "-t", str(DURACAO_MAX), "-shortest",
            "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-profile:v", "high", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(destino)]
    subprocess.run(cmd, check=True)
    moldura.unlink(missing_ok=True)
    return destino
