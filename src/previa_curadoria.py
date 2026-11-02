"""Prévia da curadoria nova (02/11/2026): busca de verdade, mas NÃO grava fila nem memória.

Mostra o que a regra nova mandaria para o Instagram hoje e quais produtos que já estão na fila
(escolhidos pela regra antiga) ela barraria. Gera folhas com as fotos em previa_curadoria/.

Uso: python -m src.previa_curadoria
"""
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import awin, busca_profunda, config, curadoria, garimpar, imagem, variedade

SAIDA = Path("previa_curadoria")
FONTE = Path("assets/fontes")


def _fonte(tam, negrito=False):
    p = FONTE / "Poppins-Bold.ttf" if negrito else Path("assets/Montserrat.ttf")
    return ImageFont.truetype(str(p), tam) if p.exists() else ImageFont.load_default()


def folha(itens, titulo, arquivo, cor=(70, 45, 20)):
    """Grade 3 colunas: foto, nome, preço, notas e o motivo (gancho)."""
    if not itens:
        return None
    col, larg, alt_foto, alt_txt = 3, 360, 360, 190
    linhas = (len(itens) + col - 1) // col
    img = Image.new("RGB", (col * larg, 90 + linhas * (alt_foto + alt_txt)), (250, 246, 238))
    d = ImageDraw.Draw(img)
    d.text((20, 25), titulo, font=_fonte(34, True), fill=cor)
    f_nome, f_info = _fonte(19, True), _fonte(17)
    for i, o in enumerate(itens):
        x, y = (i % col) * larg, 90 + (i // col) * (alt_foto + alt_txt)
        try:
            foto = imagem._baixar_foto(o["imagem"]).convert("RGB")
            foto.thumbnail((larg - 20, alt_foto - 10))
            img.paste(foto, (x + (larg - foto.width) // 2, y + 5))
        except Exception:
            d.text((x + 20, y + 150), "(foto não baixou)", font=f_info, fill=(120, 0, 0))
        ty = y + alt_foto + 2
        for ln in textwrap.wrap(o["nome"], 30)[:2]:
            d.text((x + 12, ty), ln, font=f_nome, fill=(30, 30, 30))
            ty += 23
        foto_n = f" | foto {o['foto_nota']:.0f}" if o.get("foto_nota") is not None else ""
        d.text((x + 12, ty + 2), f"R$ {o.get('preco_fmt', '?')} | uau {o.get('uau', 0):.0f}{foto_n} | {o.get('vendas', 0)} vendas",
               font=f_info, fill=(60, 40, 10))
        ty += 26
        for ln in textwrap.wrap(f"“{o.get('gancho') or 'sem motivo: comum'}”", 34)[:3]:
            d.text((x + 12, ty), ln, font=f_info, fill=(20, 90, 40) if o.get("gancho") else (150, 30, 30))
            ty += 21
    SAIDA.mkdir(exist_ok=True)
    img.save(SAIDA / arquivo, "JPEG", quality=85)
    return SAIDA / arquivo


def main():
    fila = garimpar.carregar_fila()
    garimpar.limpar_fila(fila)

    # 1) o que já está esperando na fila (regra antiga) — a regra nova reavalia pelo nome e pela foto
    pend = [dict(o) for o in fila["ofertas"].values()
            if o.get("status") == "pendente" and o.get("nome") and not o.get("pedido") and not o.get("video_manual")]
    antigos_ig = [o for o in pend if variedade.diferenciado(o) and not o.get("so_telegram")
                  and o.get("nivel") in ("ouro", "achado")]
    print(f"\n===== FILA ATUAL: {len(antigos_ig)} produtos prontos para o Instagram pela regra antiga =====")
    reav = [dict(o) for o in antigos_ig]
    shopee_ae = [o for o in reav if o.get("origem_busca") != "marca"]
    marcas_ = [o for o in reav if o.get("origem_busca") == "marca"]
    ganchos = {}
    notas = curadoria.notas_uau(shopee_ae, ganchos=ganchos)
    for o in shopee_ae:
        o["uau_antigo"] = o.get("uau")
        o["uau"] = notas.get(o["id"], o["uau"])
        o["gancho"] = ganchos.get(o["id"], "")
        o["uau"] = variedade.uau(o)
    garimpar.julgar_marcas(marcas_)
    garimpar.olhar_fotos(reav)
    fica = [o for o in reav if variedade.para_instagram(o)]
    sai = [o for o in reav if not variedade.para_instagram(o)]
    for o in sorted(reav, key=lambda o: -o.get("uau", 0)):
        print(f"{'✅ fica' if o in fica else '❌ sai '} uau {o.get('uau_antigo', 8)}→{o['uau']:.0f}"
              f"{' foto ' + format(o['foto_nota'], '.0f') if o.get('foto_nota') is not None else ''}"
              f"  {o['nome'][:70]}  | {o.get('gancho') or '(sem motivo)'}")
    folha(sai, f"Regra nova TIRA do Instagram ({len(sai)} de {len(reav)} da fila de hoje)", "1-sai-da-fila.jpg", (150, 30, 30))
    folha(fica, f"Da fila de hoje, FICAM ({len(fica)})", "2-fica-da-fila.jpg", (20, 90, 40))

    # 2) garimpo novo com a regra nova (sem gravar nada)
    print("\n===== GARIMPO NOVO (regra nova, nada é gravado) =====")
    mem = busca_profunda.carregar()
    escolhidas = busca_profunda.escolher_palavras(mem)
    candidatos = garimpar.curar(fila, garimpar.coletar_candidatos(fila, escolhidas=escolhidas, mem=mem))
    candidatos += awin.candidatos(fila, garimpar.ja_usado, julgar=garimpar.julgar_marcas)
    ig = [o for o in candidatos if variedade.para_instagram(o)]
    escolhidos = garimpar.selecionar(ig, 15, variedade.contar_pendentes(fila), {})
    escolhidos.sort(key=lambda o: o.get("pontos", 0), reverse=True)
    for o in escolhidos:
        print(f"⭐ uau {o['uau']:.0f} foto {o.get('foto_nota', '-')}  R$ {o['preco_fmt']}  {o['nome'][:70]}  | {o.get('gancho')}")
    print(f"\nTotal que passaria para o Instagram nesta rodada: {len(ig)} (antes de tirar repetidos); escolhidos: {len(escolhidos)}")
    folha(escolhidos, f"Regra nova: o que entraria no Instagram ({len(escolhidos)})", "3-novos-regra-nova.jpg", (20, 90, 40))
    barrados_foto = [o for o in candidatos if o.get("foto_nota") is not None and o["foto_nota"] < config.FOTO_MINIMA][:9]
    folha(barrados_foto, "Uau alto, mas foto fraca → só Telegram", "4-foto-fraca.jpg", (150, 90, 20))


if __name__ == "__main__":
    main()
