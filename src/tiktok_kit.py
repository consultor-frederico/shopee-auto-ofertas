"""Kit do TikTok (31/10/2026): enquanto o app do TikTok não passa na auditoria (antes disso a API só posta como
privado), o robô manda no Telegram privado do Fred os slides do carrossel em versão TikTok (Modo Foto) e a
legenda pronta. O Fred posta do celular, escolhendo a música em alta no app.

Nos slides do TikTok o "comente QUERO" vira "digite #142 no link do perfil" (src/numeros.py), porque lá
comentário não tem link clicável e o direct só funciona entre quem se segue.
Desligar: TIKTOK_KIT=0. Precisa de TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_PRIVADO.
"""
import json
import os
from pathlib import Path

from . import config, marcas

LIGADO = os.getenv("TIKTOK_KIT", "1") != "0"
TAGS_CATEGORIA = {"lar": "#casaorganizada #utilidadesdomesticas", "pet": "#pet #achadinhospet",
                  "eletronicos": "#tecnologia #gadgets", "brinquedos": "#brinquedos #presentecrianca",
                  "automotivo": "#carro #acessoriosautomotivos", "masculino": "#presentemasculino #homem",
                  "beleza": "#beleza #maquiagem", "cabelo": "#cabelo #cuidadoscomcabelo",
                  "moda": "#moda #lookdodia", "autocuidado": "#autocuidado #selfcare",
                  "casa_fofa": "#decoracao #quartoaesthetic"}
NOME_LOJA = {"shopee": "Shopee", "aliexpress": "AliExpress", **{p: m["nome"] for p, m in marcas.MARCAS.items()}}


def ligado():
    return LIGADO and config.PERFIL == "garimpo"


def _preco(o):
    try:
        return float(str(o.get("preco_fmt", "0")).replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def linha_busca(ofertas, tema=None):
    """1ª linha da legenda com as palavras que o comprador digita na busca (TikTok e Instagram):
    'Achadinhos Shopee e AliExpress até R$ 190: organizador de pia, fone bluetooth e mais'."""
    lojas = []
    for o in ofertas:
        nome = NOME_LOJA.get(o.get("plataforma") or "shopee", "Shopee")
        if nome not in lojas:
            lojas.append(nome)
    teto = max(_preco(o) for o in ofertas)
    nomes = [o.get("titulo") or o.get("nome", "") for o in ofertas]
    assunto = f"{tema.lower()}" if tema else ", ".join(nomes[:2]) + (" e mais" if len(nomes) > 2 else "")
    lojas_txt = ", ".join(lojas[:-1]) + " e " + lojas[-1] if len(lojas) > 1 else lojas[0]
    teto_txt = f"{teto:,.0f}".replace(",", ".")
    return f"Achadinhos {lojas_txt} até R$ {teto_txt}: {assunto}"


def legenda(ofertas, tema=None):
    """Legenda pensada para a busca do TikTok: as palavras que o comprador digita na lupa vêm primeiro."""
    linhas = [linha_busca(ofertas, tema).replace("#", "") + " 🤠⛏️", ""]
    for o in ofertas:
        # sem "#" no número: no TikTok "#142" vira hashtag e conta no limite de 5
        nome = (o.get("titulo") or o.get("nome") or "").replace("#", "")
        linhas.append(f"Nº {o.get('num', '?')} {nome} — R$ {o.get('preco_fmt')}")
    linhas += ["", f"👉 Gostou? Digite o número (Nº) do achado no link do perfil ({config.PAGINA_BIO}) e abre direto na loja.",
               "Preços do dia do post, podem mudar na loja. Links de afiliado: você paga o mesmo.", ""]
    cats = []
    for o in ofertas:
        t = TAGS_CATEGORIA.get(o.get("categoria"))
        if t and t not in cats:
            cats.append(t)
    tags = ["#achadinhos", "#achadinhosshopee", "#garimpovip"]   # TikTok aceita no máximo 5 hashtags
    for t in " ".join(cats).split():
        if len(tags) < 5 and t not in tags:
            tags.append(t)
    linhas.append(" ".join(tags))
    return "\n".join(linhas)


def _postar_api(arquivos, texto):
    """Se os segredos do TikTok estão cadastrados (src/tiktok.py), manda as fotos pela API antes do kit.
    Devolve o aviso que vai no álbum do Telegram ('' se a API está desligada)."""
    from . import tiktok
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    if not (tiktok.ligado() and base):
        return ""
    site = config.RAIZ / "site"
    try:
        urls = [f"{base}/{Path(a).resolve().relative_to(site.resolve()).as_posix()}" for a in arquivos]
        titulo = texto.split("\n", 1)[0]
        _, situacao = tiktok.postar_fotos(urls, titulo, texto)
        print(f"🎵 TikTok pela API ({tiktok.modo()}): {situacao}")
        if tiktok.modo() == "rascunho":
            return ("🎵 TikTok: as fotos já estão na caixa de entrada do app (notificação). Abre, escolhe a música "
                    "em alta, cola a legenda daqui de baixo e posta.")
        return "🎵 TikTok: já postado pela API (privado até a auditoria). As fotos e a legenda seguem aqui."
    except Exception as e:   # nunca derruba o post do Instagram; o kit manual vai do mesmo jeito
        print(f"::warning::TikTok pela API não foi: {e}")
        return f"⚠️ A API do TikTok falhou ({str(e)[:150]}). Posta pelo kit: salva as fotos e escolhe a música."


def enviar(arquivos, texto):
    """Fotos (até 10) num álbum e, logo depois, a legenda numa mensagem separada (fácil de copiar)."""
    if not ligado() or not arquivos:
        return
    aviso = _postar_api(arquivos, texto)
    from . import telegram, whatsapp_kit
    chat = whatsapp_kit.chat_privado()
    if not (chat and os.getenv("TELEGRAM_BOT_TOKEN", "").strip()):
        print("⏸️  Kit do TikTok: falta TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_PRIVADO.")
        return
    try:
        abertos = [open(a, "rb") for a in arquivos[:10]]
        try:
            midia = [{"type": "photo", "media": f"attach://f{i}"} for i in range(len(abertos))]
            midia[0]["caption"] = aviso or (f"🎵 Kit do TikTok {config.ARROBA_TIKTOK} (Modo Foto): salva as fotos, "
                                             "posta e escolhe uma música em alta.")
            telegram._api("sendMediaGroup", data={"chat_id": chat, "media": json.dumps(midia)},
                          files={f"f{i}": f for i, f in enumerate(abertos)})
        finally:
            for f in abertos:
                f.close()
        telegram._api("sendMessage", data={"chat_id": chat, "text": texto[:4000]})
        print("🎵 Kit do TikTok enviado no Telegram privado.")
    except Exception as e:   # nunca derruba o post do Instagram
        print(f"::warning::Kit do TikTok não foi: {e}")
