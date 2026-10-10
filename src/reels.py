"""Gera um Reels (1080x1920, ~8s, MP4 H.264) a partir da foto da oferta, sem música.

Linha do tempo:
  0,0s  GANCHO em letras grandes no topo (segura quem está rolando o feed) + foto com zoom lento
  2,4s  o gancho sobe e o logo aparece
  0,6s  título entra
  1,4s  preço entra deslizando
  2,2s  selo de desconto "salta"
  2,8s  nota e vendas
  3,6s  faixa "COMENTE EU QUERO" sobe e pulsa até o fim

No Garimpo VIP há 4 estilos (ESTILOS: cores, movimento da foto e animações diferentes).
O robô alterna entre eles sem repetir nenhum dos 2 últimos Reels (data/reels_estilo.json).
Fixar um estilo: variável REELS_ESTILO=classico|noite|ouro|vitrine.
"""
import json
import os
import math
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageOps

from . import config
from .imagem import (FUNDO, SOMBRA, BRANCO, CINZA, DOURADO, DOURADO_CLARO, ESCURO, LARANJA,
                     _baixar_foto, _brl, _estrela, _fonte, eh_achado,
                     moldura_achado, selo_achado, selo_loja)

L, A = 1080, 1920
FPS = 30
DURACAO = 8.0


# ------------------------------------------------------------------ estilos
_BASE = {"fundo": FUNDO, "sombra": SOMBRA, "cartao": BRANCO, "borda": None, "titulo": ESCURO,
         "preco": LARANJA, "rs": DOURADO, "info": CINZA, "estrela": DOURADO,
         "cta_fundo": ESCURO, "cta1": BRANCO, "cta2": DOURADO_CLARO, "cta_sub": "#CFC6B8",
         "gancho_fundo": ESCURO, "gancho2": DOURADO_CLARO, "logo_fundo": None,
         "foto": "zoom_in", "cartao_entra": None, "titulo_de": "esquerda", "preco_anim": "sobe",
         "selo_lado": "direita", "cta": "faixa"}
ESTILOS = {
    # o visual original: fundo claro, foto aproximando devagar
    "classico": {},
    # fundo escuro, foto se afastando, título vindo da direita, faixa dourada
    "noite": {"fundo": "#24150A", "sombra": "#0E0803", "titulo": "#F3EBDD", "preco": "#E2BE68",
              "rs": "#E2BE68", "info": "#CFC6B8", "estrela": "#E2BE68", "cta_fundo": "#A07E30",
              "cta1": "#24150A", "cta2": BRANCO, "cta_sub": "#2E1D0D", "gancho_fundo": "#A07E30",
              "gancho2": "#24150A", "logo_fundo": "#EEEDE9", "foto": "zoom_out",
              "titulo_de": "direita", "selo_lado": "esquerda"},
    # fundo dourado claro, cartão sobe no começo, preço "salta", chamada em pílula
    "ouro": {"fundo": "#F3E3B8", "sombra": "#DCC48A", "titulo": "#24150A", "info": "#6B5532",
             "estrela": "#A07E30", "gancho_fundo": "#A07E30", "gancho2": "#24150A",
             "foto": "pan", "cartao_entra": "baixo", "titulo_de": "cima", "preco_anim": "pop",
             "cta": "pilula"},
    # vitrine: cartão com moldura dourada que entra pela direita, preço vindo da esquerda
    "vitrine": {"borda": "#A07E30", "cta_fundo": "#A07E30", "cta1": BRANCO, "cta2": "#24150A",
                "cta_sub": "#F3EBDD", "foto": "pan_v", "cartao_entra": "direita",
                "preco_anim": "esquerda", "selo_lado": "esquerda"},
}
ARQ_ESTILO = config.PASTA_DADOS / "reels_estilo.json"


def escolher_estilo(oferta=None):
    """Estilo da vez: alterna e nunca repete o do Reels anterior. Só no Garimpo VIP."""
    if config.PERFIL != "garimpo":
        return "classico"
    fixo = os.getenv("REELS_ESTILO", "").strip().lower()
    if fixo in ESTILOS:
        return fixo
    try:
        recentes = json.loads(ARQ_ESTILO.read_text(encoding="utf-8")).get("recentes", [])
    except Exception:
        recentes = []
    # não repete nenhum dos 2 últimos, para os 4 estilos irem girando
    opcoes = [e for e in ESTILOS if e not in recentes[-2:]] or list(ESTILOS)
    semente = sum((i + 3) * ord(c) for i, c in enumerate(str((oferta or {}).get("id", ""))))
    escolhido = opcoes[semente % len(opcoes)]
    try:
        ARQ_ESTILO.write_text(json.dumps({"recentes": (recentes + [escolhido])[-3:]}), encoding="utf-8")
    except Exception:
        pass
    return escolhido


def _estilo(nome):
    return {**_BASE, **ESTILOS.get(nome, {})}


def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _pop(t):
    """Escala com leve "quique": 0 → ~1.05 → 1."""
    t = max(0.0, min(1.0, t))
    return _ease(t) + 0.15 * math.sin(math.pi * t)


def _fundo_estatico(oferta, foto, e=None):
    """Partes que não se mexem: fundo e logo."""
    e = e or _estilo("classico")
    base = Image.new("RGB", (L, A), e["fundo"])
    try:
        logo = Image.open(config.LOGO).convert("RGBA")
        logo = ImageOps.contain(logo, (340, 200), Image.LANCZOS)
        x, y = (L - logo.width) // 2, 70
        if e["logo_fundo"]:
            ImageDraw.Draw(base).rounded_rectangle([x - 36, y - 6, x + logo.width + 36, y + logo.height + 4],
                                                   60, fill=e["logo_fundo"])
        base.paste(logo, (x, y), logo)
    except Exception:
        pass
    return base


def _quadro(t, base, foto, oferta, e=None):
    e = e or _estilo("classico")
    F = e["fundo"]
    img = base.copy()
    d = ImageDraw.Draw(img)

    # Cartão da foto (pode entrar deslizando no começo)
    cx0, cy0, cx1, cy1 = 70, 300, L - 70, 300 + 940
    if e["cartao_entra"] and t < 0.6:
        k = 1 - _ease(t / 0.6)
        dx, dy = (int(k * L), 0) if e["cartao_entra"] == "direita" else (0, int(k * 900))
        cx0, cx1, cy0, cy1 = cx0 + dx, cx1 + dx, cy0 + dy, cy1 + dy
    d.rounded_rectangle([cx0 + 6, cy0 + 10, cx1 + 6, cy1 + 10], 44, fill=e["sombra"])
    d.rounded_rectangle([cx0, cy0, cx1, cy1], 44, fill=e["cartao"])
    if foto is not None:
        jan_w, jan_h = cx1 - cx0 - 40, cy1 - cy0 - 40
        prog = t / DURACAO
        if e["foto"] in ("pan", "pan_v"):
            # passeia pela foto (horizontal ou vertical) com ela um pouco ampliada
            z = 1.18
            f = ImageOps.contain(foto, (int((cx1 - cx0 - 80) * z), int((cy1 - cy0 - 80) * z)), Image.BILINEAR)
            sobra_x, sobra_y = max(0, f.width - jan_w), max(0, f.height - jan_h)
            k = _ease(prog) if e["foto"] == "pan" else 1 - _ease(prog)
            ox = int(sobra_x * k) if e["foto"] == "pan" else sobra_x // 2
            oy = int(sobra_y * k) if e["foto"] == "pan_v" else sobra_y // 2
        else:
            z = 1 + 0.08 * (prog if e["foto"] == "zoom_in" else 1 - prog)
            f = ImageOps.contain(foto, (int((cx1 - cx0 - 80) * z), int((cy1 - cy0 - 80) * z)), Image.BILINEAR)
            ox, oy = max(0, (f.width - jan_w) // 2), max(0, (f.height - jan_h) // 2)
        # recorta o excesso para não vazar do cartão
        f = f.crop((ox, oy, ox + min(f.width, jan_w), oy + min(f.height, jan_h)))
        img.paste(f, (cx0 + (cx1 - cx0 - f.width) // 2, cy0 + (cy1 - cy0 - f.height) // 2))
    if e["borda"]:
        d.rounded_rectangle([cx0, cy0, cx1, cy1], 44, outline=e["borda"], width=14)

    # Selo da loja (fica do lado oposto ao selo de desconto)
    esq = e["selo_lado"] == "esquerda"
    loja_x = cx0 + 30
    if esq:   # mede a pílula num rascunho para encostá-la no canto direito
        loja_x = cx1 - 30 - selo_loja(ImageDraw.Draw(Image.new("RGB", (8, 8))), oferta, 0, 0, escala=1.1)
    selo_loja(d, oferta, loja_x, cy0 + 30, escala=1.1)
    if eh_achado(oferta):   # 💎 achado escondido: moldura turquesa + faixa no pé da foto
        moldura_achado(d, (cx0, cy0, cx1, cy1), 44, escala=1.1)
        selo_achado(d, cx0 + 30, cy1 - 30 - int(92 * 1.1), escala=1.1)

    # Selo de desconto
    if oferta.get("desconto") and t >= 2.2:
        s = _pop((t - 2.2) / 0.45)
        r = int(120 * s)
        if r > 8:
            sx, sy = (cx0 + 50 if esq else cx1 - 50), cy0 + 50
            d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=DOURADO, outline=BRANCO, width=8)
            if s > 0.7:
                f1, f2 = _fonte(int(74 * s), "Black"), _fonte(int(38 * s), "Bold")
                t1, t2 = f"-{oferta['desconto']}%", "OFF"
                d.text((sx - d.textlength(t1, font=f1) / 2, sy - 62 * s), t1, font=f1, fill=BRANCO)
                d.text((sx - d.textlength(t2, font=f2) / 2, sy + 22 * s), t2, font=f2, fill=BRANCO)

    # Título
    y = cy1 + 60 if not e["cartao_entra"] else 300 + 940 + 60
    if t >= 0.6:
        k = _ease((t - 0.6) / 0.5)
        f_tit = _fonte(60, "ExtraBold")
        tx, ty = 70, y
        if e["titulo_de"] == "esquerda":
            tx -= (1 - k) * 300
        elif e["titulo_de"] == "direita":
            tx += (1 - k) * 300
        else:
            ty -= (1 - k) * 60
        d.text((tx, ty), oferta["titulo"], font=f_tit, fill=_mix(F, e["titulo"], k))

    # Preço
    y2 = y + 100
    if t >= 1.4:
        k = _ease((t - 1.4) / 0.5)
        dx, dy, esc = 0, 0, 1.0
        if e["preco_anim"] == "sobe":
            dy = (1 - k) * 80
        elif e["preco_anim"] == "esquerda":
            dx = -(1 - k) * 500
        else:   # pop
            esc = max(0.3, _pop((t - 1.4) / 0.45))
            k = min(1.0, k * 1.6)
        x = 70 + dx
        f_de, f_rs, f_preco = _fonte(42, "Medium"), _fonte(54, "Bold"), _fonte(int(130 * esc), "Black")
        if oferta.get("preco_de"):
            de = f"R$ {_brl(oferta['preco_de'])}"
            d.text((x, y2 + 50 + dy), de, font=f_de, fill=_mix(F, e["info"], k))
            w = d.textlength(de, font=f_de)
            d.line([x - 4, y2 + 77 + dy, x + w + 4, y2 + 77 + dy], fill=_mix(F, e["info"], k), width=5)
            x += w + 30
        d.text((x, y2 + 44 + dy), "R$", font=f_rs, fill=_mix(F, e["rs"], k))
        x += d.textlength("R$", font=f_rs) + 12
        d.text((x, y2 + 110 - 130 * esc + dy), oferta["preco_fmt"], font=f_preco, fill=_mix(F, e["preco"], k))

    # Nota e vendas
    if t >= 2.8:
        k = _ease((t - 2.8) / 0.4)
        yi = y2 + 175
        cor = _mix(F, e["info"], k)
        _estrela(d, 70 + 22, yi + 25, 24, _mix(F, e["estrela"], k))
        nota = (f"{oferta['avaliacao_pct']:.0f}% aprovação" if oferta.get("avaliacao_pct")
                else f"{oferta['nota']:.1f}".replace(".", ","))
        vendas = f"{oferta['vendas']:,}".replace(",", ".")
        d.text((70 + 54, yi), f"{nota}   •   {vendas}+ vendidos", font=_fonte(40, "SemiBold"), fill=cor)

    # Chamada (faixa no pé ou pílula flutuante; sobe e pulsa)
    if t >= 3.6:
        k = _ease((t - 3.6) / 0.4)
        h = 170
        if e["cta"] == "pilula":
            topo = A - (h + 40) * k
            d.rounded_rectangle([50, topo, L - 50, topo + h - 10], 80, fill=e["cta_fundo"])
        else:
            topo = A - h * k
            d.rectangle([0, topo, L, A], fill=e["cta_fundo"])
        pulso = 1 + 0.05 * math.sin((t - 4.0) * 2 * math.pi * 1.1) if t > 4.0 else 1
        f_cta = _fonte(int(52 * pulso), "ExtraBold")
        partes = [("COMENTE ", e["cta1"]), ("EU QUERO", e["cta2"])]
        x = (L - sum(d.textlength(p, font=f_cta) for p, _ in partes)) / 2
        for p, cor in partes:
            d.text((x, topo + 30), p, font=f_cta, fill=cor)
            x += d.textlength(p, font=f_cta)
        f2 = _fonte(36, "SemiBold")
        sub = "que eu te mando o link no direct"
        d.text(((L - d.textlength(sub, font=f2)) / 2, topo + 100), sub, font=f2, fill=e["cta_sub"])
    _gancho(d, t, oferta, e)
    return img


GANCHOS = ["VOCÊ NÃO SABIA|QUE PRECISAVA DISSO", "OLHA O QUE EU|ACHEI NA {loja}", "ISSO AQUI|É GENIAL",
           "PARA TUDO|E OLHA ISSO", "ACHADO DO DIA|NA {loja}", "QUEM INVENTOU ISSO|MERECE UM PRÊMIO"]


def gancho(oferta):
    """Frase do primeiro segundo (2 linhas). Achado escondido tem a sua própria."""
    if eh_achado(oferta):
        return ["ACHADO QUE POUCA", "GENTE CONHECE"]
    loja = "ALIEXPRESS" if oferta.get("plataforma") == "aliexpress" else "SHOPEE"
    g = GANCHOS[sum(map(ord, str(oferta.get("id", "")))) % len(GANCHOS)]
    return g.format(loja=loja).split("|")


def _gancho(d, t, oferta, e=None):
    """Faixa do gancho no topo: aparece já no 1º quadro e sobe para fora em 2,4–2,9s."""
    if t >= 2.9:
        return
    k = _ease((t - 2.4) / 0.5) if t > 2.4 else 0
    linhas = gancho(oferta)
    f = _fonte(66, "Black")
    h = 250
    y0 = 30 - k * (h + 60)
    e = e or _estilo("classico")
    cor = "#0E7C86" if eh_achado(oferta) else e["gancho_fundo"]
    d.rounded_rectangle([40, y0, L - 40, y0 + h], 36, fill=cor)
    for i, txt in enumerate(linhas):
        while d.textlength(txt, font=f) > L - 140 and f.size > 40:
            f = _fonte(f.size - 4, "Black")
        cor_txt = e["gancho2"] if i == 1 and not eh_achado(oferta) else BRANCO
        d.text(((L - d.textlength(txt, font=f)) / 2, y0 + 38 + i * 92), txt, font=f, fill=cor_txt)


def _mix(c1, c2, k):
    k = max(0.0, min(1.0, k))
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def gerar(oferta: dict, destino, foto: Image.Image = None, estilo: str = None):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            raise RuntimeError("ffmpeg não encontrado (instale ffmpeg ou imageio-ffmpeg).")
    if foto is None:
        try:
            foto = _baixar_foto(oferta["imagem"])
        except Exception as e:
            print(f"⚠️  Reels sem foto ({e}).")
    if config.PERFIL == "ana":   # a Ana tem visual próprio (src/layout_ana.py)
        from . import layout_ana
        return layout_ana.gerar_reels(oferta, destino, foto, duracao=DURACAO, fps=FPS)
    estilo = estilo or escolher_estilo(oferta)
    oferta["estilo_reels"] = estilo
    e = _estilo(estilo)
    print(f"🎨 Estilo do Reels: {estilo}")
    base = _fundo_estatico(oferta, foto, e)
    cmd = [ffmpeg, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{L}x{A}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
           "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "128k", str(destino)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(DURACAO * FPS)):
        proc.stdin.write(_quadro(i / FPS, base, foto, oferta, e).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falhou ao gerar o Reels.")
    return destino
