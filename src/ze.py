"""Zé Garimpo, o mascote do Garimpo VIP.

1) Começo ou final dos Reels, em rodízio de 3: dois Reels de oferta terminam com uma vinheta
   curtinha do Zé (assets/ze/finais/*.mp4) e o terceiro abre com 1,8 s dele (assets/ze/inicios/*.mp4,
   sem fala, para prender quem está rolando o feed). Nunca os dois no mesmo Reels.
   O robô alterna os clipes, sem repetir o do post anterior.
   O Reels inteiro ganha trilha de assets/musicas/: várias faixas diferentes emendadas com
   transição suave (sem abrir com a mesma do Reels anterior), mais baixas quando o Zé fala.
2) Post do Zé todo dia (ZE_DIAS; desde 27/10/2026, antes seg/qua/sex/dom): um filminho de assets/ze/ze_*.mp4 vira Reels (Instagram,
   story, página do Facebook e YouTube Shorts). Vídeo novo que ainda não saiu vai primeiro;
   depois o robô repete o que está há mais tempo sem sair. O post é apagado depois de 15 dias
   (src/limpeza.py), junto com as ofertas.

  python -m src.ze preparar   → se hoje é dia do Zé, copia o vídeo da vez para site/
  python -m src.ze publicar   → publica e registra em data/ze.json
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

from . import config

ANA = config.PERFIL == "ana"   # na @ananovoachados quem aparece é a Ana (assets/ana/videos/)
PASTA = config.RAIZ / "assets" / ("ana/videos" if ANA else "ze")
PREFIXO = "ana_" if ANA else "ze_"
PASTA_FINAIS = PASTA / "finais"
PASTA_INICIOS = PASTA / "inicios"
ARQ = config.PASTA_PERFIL / "ze.json"              # cada conta com o seu rodízio
ARQ_PROX = config.PASTA_PERFIL / "proximo_ze.json"
PASTA_SITE = config.RAIZ / "site"
# dias da semana do post do Zé (0 = segunda ... 6 = domingo); padrão todo dia (desde 27/10/2026)
# Ana: 3 posts próprios por semana, terça, quinta e sábado (ANA_DIAS; 0 = segunda)
_DIAS = os.getenv("ANA_DIAS", "1,3,5") if ANA else os.getenv("ZE_DIAS", "0,1,2,3,4,5,6")   # Ana: terça, quinta e sábado
DIAS_SEMANA = {int(d) for d in _DIAS.split(",") if d.strip().isdigit()}
NOMES_DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
FINAL_LIGADO = os.getenv("ZE_NO_FINAL", "1") != "0"
INICIO_LIGADO = os.getenv("ZE_NO_INICIO", "1") != "0"
SEMPRE_NO_INICIO = os.getenv("ZE_SEMPRE_NO_INICIO", "1") != "0"   # 0 volta ao rodízio (2 no final, 1 no começo)
PASTA_MUSICAS = config.RAIZ / "assets" / ("ana/musicas" if ANA else "musicas")   # pasta vazia = sem música
MUSICA_LIGADA = os.getenv("MUSICA_REELS", "1") != "0"
# Ana: música ambiente, bem de fundo
VOLUME_MUSICA = float(os.getenv("VOLUME_MUSICA", "0.35" if ANA else "0.6"))

PEDIDO = ("🙋 VOCÊ PEDE, O ZÉ ACHA! Comenta aqui embaixo o produto que você procura "
          "(ex.: \"fone bluetooth\", \"air fryer\"). O Zé garimpa, posta o achado marcando você "
          "e ainda manda o link no seu direct! 👇")
LEGENDAS = [
    "🤠 Você sabe quantos achados o Zé descartou hoje pra te mostrar só os que valem? "
    "Ele peneira a Shopee e o AliExpress todo dia. Segue o Zé pra ver o que sobrou de ouro! ⛏️💎",
    "💰 Achadinho bom é achadinho garimpado! O Zé confere preço, nota e vendas antes de mostrar "
    "qualquer coisa. Segue a página pra não perder nenhum. ✨",
    "⛏️ Mais um dia de garimpo! O Zé cava, você escolhe. Segue o @garimpovip4 pra receber os achados "
    "antes de acabarem. 🛒",
    "🏆 Aqui só entra o que passou pela peneira do Zé: nota alta, vendas e preço bom. "
    "Segue pra ver o próximo achado! 💎",
]
# Contagem regressiva para a Black Friday (entra sozinha nos 45 dias antes)
LEGENDAS_BF = [
    "⏳ Faltam {dias} dias pra Black Friday! O Zé já está de olho nas ofertas e vai garimpar o que vale. "
    "Segue pra não perder! ⛏️",
    "🔥 Black Friday chegando: faltam {dias} dias. O Zé separa o ouro e deixa a furada de lado. "
    "Segue a página pra ver primeiro! 💎",
    "🤠 {dias} dias pra Black Friday e o Zé já está cavando! Segue e comenta o que você quer comprar "
    "que ele procura pra você. 🛒",
]
LEGENDAS_BF_HOJE = ["🔥 É HOJE! Black Friday! O Zé está garimpando as melhores ofertas. "
                    "Fica de olho nos posts e no direct! ⛏️💎"]
HASHTAGS = "#zegarimpo #garimpovip #achadinhos #achadinhosshopee #achadosdashopee"

# Posts próprios da Ana (sem oferta): tom de amiga, sem prometer teste de produto
LEGENDAS_ANA = [
    "💚 Oi, gente! Aqui é a Ana. Todo dia eu caço achadinhos de beleza, moda, autocuidado e casa "
    "pra você não precisar ficar horas procurando. Me segue pra ver o que eu achei! ✨",
    "☕ Pausa pro cafezinho e já volto com mais achados! Me segue pra não perder nenhum. 💚",
    "🛍️ Achadinho bom é aquele que cabe no bolso e deixa o dia mais gostoso. Bora caçar achadinho juntas? "
    "Me segue e vem comigo! ✨",
    "✨ Me conta aqui nos comentários: que tipo de achadinho você quer ver mais por aqui? "
    "Eu leio tudo e caço pra você! 💬",
]
LEGENDAS_ANA_BF = [
    "⏳ Faltam {dias} dias pra Black Friday! Já estou de olho nos achadinhos de beleza, moda e casa. "
    "Me segue pra ver primeiro! 💚",
    "🔥 {dias} dias pra Black Friday! Me conta nos comentários o que você quer comprar que eu procuro pra você. ✨",
    "💚 Black Friday chegando, faltam {dias} dias. Eu separo os achados que valem e te mostro por aqui. "
    "Me segue pra não perder! 🛍️",
]
LEGENDAS_ANA_BF_HOJE = ["🔥 É HOJE! Black Friday! Estou caçando os melhores achadinhos pra você. "
                        "Fica de olho nos posts e no direct! 💚"]
PEDIDO_ANA = "💬 Comenta o que você mais gosta de ver: beleza, moda, autocuidado ou casa? Eu leio tudo! 💚"
HASHTAGS_ANA = "#ananovoachados #achadinhosfemininos #autocuidado #achadinhos #achadosdashopee"


def dias_para_black_friday(hoje=None):
    """Dias até a Black Friday (sexta depois da 4ª quinta de novembro). Negativo se já passou este ano."""
    hoje = (hoje or _agora()).date()
    nov1 = hoje.replace(month=11, day=1)
    quinta4 = nov1 + timedelta(days=(3 - nov1.weekday()) % 7 + 21)
    return ((quinta4 + timedelta(days=1)) - hoje).days


def _legenda_propria(n):
    """Legenda do post próprio: nos 45 dias antes da Black Friday entra a contagem regressiva."""
    dias = dias_para_black_friday()
    if 0 <= dias <= 45:
        if dias == 0:
            lista = LEGENDAS_ANA_BF_HOJE if ANA else LEGENDAS_BF_HOJE
        else:
            lista = LEGENDAS_ANA_BF if ANA else LEGENDAS_BF
        return lista[n % len(lista)].format(dias=dias)
    lista = LEGENDAS_ANA if ANA else LEGENDAS
    return lista[n % len(lista)]


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _carregar():
    if ARQ.exists():
        return json.loads(ARQ.read_text(encoding="utf-8"))
    return {"posts": [], "ultimo_final": ""}


def _salvar(dados):
    ARQ.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _agora():
    from .garimpar import agora
    return agora()


# ------------------------------------------------------------------ vinheta no fim dos Reels
def _escolher(pasta, chave, oferta=None):
    """Clipe da vez: alterna pela oferta e nunca repete o último usado."""
    clipes = sorted(pasta.glob("*.mp4"))
    if not clipes:
        return None
    dados = _carregar()
    ultimo = dados.get(chave, "")
    opcoes = [f for f in clipes if f.name != ultimo] or clipes
    semente = sum(map(ord, str((oferta or {}).get("id", time.time()))))
    escolhido = opcoes[semente % len(opcoes)]
    dados[chave] = escolhido.name
    _salvar(dados)
    return escolhido


def escolher_final(oferta=None):
    return _escolher(PASTA_FINAIS, "ultimo_final", oferta)


def escolher_inicio(oferta=None):
    return _escolher(PASTA_INICIOS, "ultimo_inicio", oferta)


def _duracao(arquivo):
    r = subprocess.run([_ffmpeg(), "-hide_banner", "-i", str(arquivo)], capture_output=True, text=True)
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _base_musica(nome):
    """'toys_are_us_2.mp3' → 'toys_are_us' (trechos da mesma música)."""
    import re
    return re.sub(r"(_\d+)?\.mp3$", "", nome or "")


def escolher_musicas(oferta=None, total=30.0):
    """Trilha da vez: uma sequência de músicas diferentes de assets/musicas/ para cobrir o Reels.
    Começa por uma faixa diferente da que abriu o Reels anterior e vai trocando de música
    a cada volta (só repete depois de usar todas)."""
    import random
    musicas = sorted(PASTA_MUSICAS.glob("*.mp3"))
    if not musicas:
        return []
    dados = _carregar()
    ultima = dados.get("ultima_musica", "")
    rnd = random.Random(str((oferta or {}).get("id", time.time())) + ultima)
    fila, lista, cobre = [], [], 0.0
    while cobre < total + 1:
        if not fila:
            fila = musicas[:]
            rnd.shuffle(fila)
            anterior = lista[-1].name if lista else ultima
            if len(fila) > 1 and fila[0].name == anterior:
                fila.append(fila.pop(0))
        # não emenda dois trechos da mesma música (toys_are_us_1 e toys_are_us_2)
        prev = _base_musica(lista[-1].name if lista else ultima)
        k = next((i for i, x in enumerate(fila) if _base_musica(x.name) != prev), 0)
        m = fila.pop(k)
        lista.append(m)
        cobre += max(1.0, _duracao(m) - 1.0)
    dados["ultima_musica"] = lista[0].name
    _salvar(dados)
    return lista


def _com_musica(video, musicas, saida):
    """Emenda as músicas uma na outra com transição suave até o fim do vídeo e
    abaixa o volume sempre que há voz no vídeo (o Zé falando, ou o áudio do vídeo manual)."""
    total = _duracao(video)
    entradas = ["-i", str(video)]
    for m in musicas:
        entradas += ["-i", str(m)]
    cadeia, ult = "", "[1:a]"
    for i in range(2, len(musicas) + 1):
        cadeia += (f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo[s{i}];"
                   f"{ult}[s{i}]acrossfade=d=1:c1=tri:c2=tri[m{i}];")
        ult = f"[m{i}]"
    if len(musicas) > 1:
        cadeia = "[1:a]aresample=44100,aformat=channel_layouts=stereo[s1];" + cadeia.replace("[1:a]", "[s1]", 1)
    filtro = (f"{cadeia}{ult}aresample=44100,aformat=channel_layouts=stereo,atrim=0:{total:.2f},"
              f"volume={VOLUME_MUSICA},afade=t=out:st={max(0, total - 0.8):.2f}:d=0.8[m];"
              "[0:a]aresample=44100,aformat=channel_layouts=stereo,asplit[v][k];"
              "[m][k]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[md];"
              "[v][md]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]")
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", *entradas, "-filter_complex", filtro,
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(saida)]
    subprocess.run(cmd, check=True)


def _vez_do_ze():
    """Rodízio de 3 Reels de oferta, para o Zé não aparecer demais:
    1º e 2º → Zé só no final; 3º → Zé só no começo. Depois recomeça.
    Devolve (quer_inicio, quer_final)."""
    if SEMPRE_NO_INICIO:   # 17/10/2026: todo Reels abre com um vídeo dele(a)
        return (True, False)
    dados = _carregar()
    n = int(dados.get("ciclo_reels", 0)) % 3
    dados["ciclo_reels"] = (n + 1) % 3
    _salvar(dados)
    return (n == 2, n != 2)


def emendar_final(reels, oferta=None):
    """Cola o Zé no começo ou a vinheta no fim do Reels (rodízio de _vez_do_ze) e põe música no Reels inteiro (mesmo arquivo).
    No Garimpo VIP é o Zé; na Ana Novo Achados é a Ana. Devolve o nome da vinheta usada."""
    quer_inicio, quer_final = _vez_do_ze()
    final = escolher_final(oferta) if (FINAL_LIGADO and quer_final) else None
    inicio = escolher_inicio(oferta) if (INICIO_LIGADO and quer_inicio) else None
    partes = ([inicio] if inicio else []) + [reels] + ([final] if final else [])
    if len(partes) > 1:
        saida = reels.with_suffix(".com-ze.mp4")
        entradas, filtro, junta = [], "", ""
        for i, arq in enumerate(partes):
            entradas += ["-i", str(arq)]
            filtro += (f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                       f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v{i}];"
                       f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo[a{i}];")
            junta += f"[v{i}][a{i}]"
        filtro += f"{junta}concat=n={len(partes)}:v=1:a=1[v][a]"
        cmd = [_ffmpeg(), "-y", "-loglevel", "error", *entradas,
               "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(saida)]
        subprocess.run(cmd, check=True)
        saida.replace(reels)
        if inicio:
            print(f"{'💚 Ana' if ANA else '🤠 Zé'} no começo do Reels: {inicio.name}")
            if oferta is not None:
                oferta["inicio_ze"] = inicio.name
        if final:
            print(f"{'💚 Ana' if ANA else '🤠 Zé'} no final do Reels: {final.name}")
    musicas = escolher_musicas(oferta, _duracao(reels)) if MUSICA_LIGADA else []
    if musicas:
        try:
            saida = reels.with_suffix(".com-musica.mp4")
            _com_musica(reels, musicas, saida)
            saida.replace(reels)
            nomes = " → ".join(m.stem for m in musicas)
            if oferta is not None:
                oferta["musica"] = nomes
            print(f"🎵 Músicas no Reels: {nomes}")
        except Exception as e:
            print(f"::warning::Música não entrou ({e}); o Reels sai sem ela.")
    return final.name if final else None


# ------------------------------------------------------------------ post do Zé (ZE_DIAS)
def videos():
    return sorted(PASTA.glob(f"{PREFIXO}*.mp4"))


def video_da_vez(dados):
    """Zé: primeiro os que nunca saíram; depois o que está há mais tempo sem sair.
    Ana: sorteio entre os que nunca saíram; depois, entre a metade que está há mais tempo sem sair."""
    if ANA:
        import random
        uso = {}
        for p in dados["posts"]:
            uso[p["video"]] = max(uso.get(p["video"], ""), p["postado_em"])
        lista = videos()
        if not lista:
            return None
        novos = [v for v in lista if v.name not in uso]
        if novos:
            return random.choice(novos)
        antigos = sorted(lista, key=lambda v: uso[v.name])
        return random.choice(antigos[:max(1, len(antigos) // 2)])
    ultimo_uso = {}
    for p in dados["posts"]:
        ultimo_uso[p["video"]] = max(ultimo_uso.get(p["video"], ""), p["postado_em"])
    lista = videos()
    if not lista:
        return None
    novos = [v for v in lista if v.name not in ultimo_uso]
    if novos:
        ordem = _ordem()   # assets/ze/ordem.txt: os que você quer na frente, um por linha
        return min(novos, key=lambda v: (ordem.index(v.name) if v.name in ordem else len(ordem), v.name))
    return min(lista, key=lambda v: ultimo_uso[v.name])


def _ordem():
    arq = PASTA / "ordem.txt"
    try:
        return [l.strip() for l in arq.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    except OSError:
        return []


def dias_desde_ultimo(dados):
    from .garimpar import BRT, FMT
    if not dados["posts"]:
        return None
    ult = max(p["postado_em"] for p in dados["posts"])
    return (_agora() - datetime.strptime(ult, FMT).replace(tzinfo=BRT)).days


def _saida(chave, valor):
    arq = os.getenv("GITHUB_OUTPUT")
    if arq:
        with open(arq, "a") as f:
            f.write(f"{chave}={valor}\n")


def preparar():
    from . import instagram
    _saida("tem_post", "false")
    if not instagram.tem_token():
        print("⏸️  Token do Instagram ausente.")
        return
    dados = _carregar()
    forcar = os.getenv("FORCAR") == "1"
    hoje = _agora()
    ja_hoje = any(p["postado_em"].startswith(hoje.strftime("%Y-%m-%d")) for p in dados["posts"])
    if not forcar and (hoje.weekday() not in DIAS_SEMANA or ja_hoje):
        dias = ", ".join(NOMES_DIAS[d] for d in sorted(DIAS_SEMANA))
        print(f"⏳ {'A Ana' if ANA else 'O Zé'} posta sozinho às {dias} (uma vez no dia). Hoje não.")
        return
    video = video_da_vez(dados)
    if not video:
        print(f"⚠️  Nenhum vídeo {PREFIXO}*.mp4 em {PASTA}.")
        return
    pasta = PASTA_SITE / "midia"
    pasta.mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    for fixo in (config.RAIZ / "assets" / "paginas").glob("*.html"):
        (PASTA_SITE / fixo.name).write_text(fixo.read_text(encoding="utf-8"), encoding="utf-8")
    nome = f"{PREFIXO[:-1]}-{int(time.time())}.mp4"
    busca = ANA and "busca" in video.name   # chamada da Busca da Ana: faixa por cima + legenda #BuscaDaAna
    if busca:
        from . import busca_reels
        busca_reels.gravar_faixa(video, pasta / nome)   # já põe a música
    else:
        from . import ze_textos
        try:   # frase do roteiro gravada na tela (assets/ze/textos.json): quase todo mundo assiste sem som
            com_texto = not ANA and ze_textos.gravar(video, pasta / nome)
        except Exception as e:
            print(f"::warning::Texto na tela não entrou ({e}); o vídeo sai sem ele.")
            com_texto = False
        if not com_texto:
            shutil.copy(video, pasta / nome)
    com_trilha = "comtrilha" in video.name   # *_comtrilha.mp4 já tem trilha própria: não põe música
    # Ana: todo vídeo sem _comtrilha recebe música. Zé: só os marcados _semtrilha (os antigos já têm música gravada).
    precisa_musica = (not com_trilha) and (ANA or "semtrilha" in video.name)
    if MUSICA_LIGADA and not busca and precisa_musica:   # põe musiquinha (mais baixa quando ela fala)
        musicas = escolher_musicas({"id": video.name}, _duracao(pasta / nome))
        if musicas:
            try:
                tmp = pasta / f"tmp-{nome}"
                _com_musica(pasta / nome, musicas, tmp)
                tmp.replace(pasta / nome)
                print(f"🎵 Música: {' → '.join(m.stem for m in musicas)}")
            except Exception as e:
                print(f"::warning::Música não entrou ({e}); o vídeo sai só com a voz.")
    n = len(dados["posts"])
    if busca:
        from . import busca_reels
        leg = busca_reels.LEGENDAS[0] + "\n\n" + busca_reels.HASHTAGS
    elif ANA:
        leg = _legenda_propria(n) + "\n\n" + PEDIDO_ANA + "\n\n" + HASHTAGS_ANA
    else:
        leg = _legenda_propria(n) + "\n\n" + PEDIDO + ("\n" + config.LEMBRETE_BIO if config.LEMBRETE_BIO else "") + "\n\n" + HASHTAGS
    ARQ_PROX.write_text(json.dumps({"arquivo": f"midia/{nome}", "video": video.name, "legenda": leg},
                                   ensure_ascii=False), encoding="utf-8")
    print(f"🎬 Post {'da Ana' if ANA else 'do Zé'} preparado: {video.name}")
    _saida("tem_post", "true")


def publicar():
    from . import facebook, instagram, youtube
    from .garimpar import FMT
    from .postar import _esperar_url, legenda_facebook
    prox = json.loads(ARQ_PROX.read_text(encoding="utf-8"))
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    url = f"{base}/{prox['arquivo']}"
    _esperar_url(url)
    ig_id = instagram.conferir_conta()["user_id"]
    cont = instagram.criar_container(ig_id, prox["legenda"], video_url=url)
    instagram.aguardar_container(cont)
    media = instagram.publicar(ig_id, cont)
    reg = {"video": prox["video"], "postado_em": _agora().strftime(FMT), "id_post": media,
           "permalink": instagram.permalink(media), "status": "postado"}
    dados = _carregar()
    dados["posts"].append(reg)
    _salvar(dados)
    ARQ_PROX.unlink(missing_ok=True)
    print(f"✅ {'Ana' if ANA else 'Zé'} publicado no Instagram ({config.ARROBA}): {reg['permalink'] or media}")
    try:
        cs = instagram.criar_story(ig_id, video_url=url)
        instagram.aguardar_container(cs)
        instagram.publicar(ig_id, cs)
        print("📲 Também no story.")
    except Exception as e:
        print(f"::warning::Story do Zé falhou: {e}")
    if ANA:   # a Ana só tem Instagram (Facebook e YouTube são do Garimpo VIP)
        _salvar(dados)
        return
    if facebook.configurado():
        try:
            reg["fb_post"] = facebook.postar_video(url, legenda_facebook(prox["legenda"]))
            print(f"📘 Zé na página do Facebook ({reg['fb_post']}).")
        except Exception as e:
            print(f"::warning::Facebook falhou: {e}")
    if youtube.configurado():
        try:
            corpo = prox["legenda"].split("\n\n#")[0]
            reg["yt_video"] = youtube.enviar_video(
                PASTA_SITE / prox["arquivo"], "Zé Garimpo achando ofertas pra você! ⛏️ #shorts",
                f"{corpo}\n\n📣 Ofertas com link direto no Telegram: {youtube.TELEGRAM}\n\n{HASHTAGS} #shorts",
                ["zé garimpo", "achadinhos", "shopee", "ofertas"])
            print(f"▶️  Zé no YouTube Shorts: https://youtube.com/shorts/{reg['yt_video']}")
        except Exception as e:
            print(f"::warning::YouTube falhou: {e}")
    _salvar(dados)


if __name__ == "__main__":
    acao = {"preparar": preparar, "publicar": publicar}.get(sys.argv[1] if len(sys.argv) > 1 else "")
    if not acao:
        print("Uso: python -m src.ze preparar|publicar")
        sys.exit(2)
    try:
        acao()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
