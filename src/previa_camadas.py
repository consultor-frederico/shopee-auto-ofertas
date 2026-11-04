"""Prévia das duas camadas (src/camadas.py): garimpo de verdade, mas NÃO grava fila nem memória e não posta nada.

Mostra quantos ⭐ especiais e 🏷️ conhecidos entrariam numa rodada, monta um carrossel de exemplo com a regra nova
(especiais na frente, conhecidos completando) e as artes com e sem o selo "ACHADO DO ZÉ".
Saída em previa_camadas/.

Uso: CAMADAS=1 python -m src.previa_camadas
"""
import os
from pathlib import Path

from PIL import Image

from . import achados_artes as artes, awin, busca_profunda, camadas, garimpar, imagem, previa_curadoria, variedade

SAIDA = Path("previa_camadas")


def _folha(itens, titulo, arquivo, cor):
    previa_curadoria.SAIDA = SAIDA
    for o in itens:   # o motivo do conhecido aparece no lugar do gancho
        if camadas.motivo_conhecido(o) and not camadas.especial(o):
            o["gancho"] = f"🏷️ {camadas.motivo_conhecido(o)}" + (f" · {o['gancho']}" if o.get("gancho") and not o["gancho"].startswith("🏷️") else "")
    return previa_curadoria.folha(itens, titulo, arquivo, cor)


def _grade(arquivos, destino, por_linha=3):
    ims = [Image.open(a).convert("RGB") for a in arquivos]
    if not ims:
        return
    w, h = 360, 450
    linhas = (len(ims) + por_linha - 1) // por_linha
    g = Image.new("RGB", (por_linha * (w + 10) + 10, linhas * (h + 10) + 10), (40, 26, 10))
    for i, im in enumerate(ims):
        g.paste(im.resize((w, h), Image.LANCZOS), (10 + (i % por_linha) * (w + 10), 10 + (i // por_linha) * (h + 10)))
    g.save(destino, "JPEG", quality=88)


def carrossel_exemplo(escolhidos):
    """Carrossel de 4 com a regra nova: especiais na frente (o 1º vira a capa), no máximo 2 conhecidos."""
    esp = [o for o in escolhidos if camadas.especial(o)]
    con = [o for o in escolhidos if not camadas.especial(o)]
    itens, fams = [], set()
    for o in esp + con:
        if len(itens) >= 4:
            break
        if variedade.familia(o) in fams:
            continue
        if not camadas.especial(o) and sum(not camadas.especial(x) for x in itens) >= camadas.CONHECIDOS_POR_CARROSSEL:
            continue
        itens.append(o)
        fams.add(variedade.familia(o))
    if not itens or not camadas.especial(itens[0]):
        print("⚠️  Sem especial para a capa: nesta rodada não sairia carrossel.")
        return []
    pasta = SAIDA / "carrossel"
    pasta.mkdir(parents=True, exist_ok=True)
    arqs = []
    for i, o in enumerate(itens, 1):
        o.setdefault("titulo", o["nome"][:40])
        try:
            foto = imagem._baixar_foto(o["imagem"])
        except Exception as e:
            print(f"⚠️  foto de {o['nome'][:40]} não baixou ({e})")
            continue
        if i == 1:
            artes.capa_produto(o, foto, len(itens) - 1, "joia", pasta / "1-capa.jpg")
            arqs.append(pasta / "1-capa.jpg")
            continue
        destino = pasta / f"{i}-{'especial' if camadas.especial(o) else 'conhecido'}.jpg"
        artes.produto_garimpo(0, o, foto, i, destino)
        arqs.append(destino)
    # arte do Telegram/WhatsApp: um especial (com selo) e um conhecido (arte normal)
    for tipo, lista in (("especial", esp), ("conhecido", con)):
        if lista:
            o = lista[0]
            o.setdefault("titulo", o["nome"][:40])
            try:
                imagem.gerar(o, SAIDA / f"telegram-{tipo}.jpg", foto=imagem._baixar_foto(o["imagem"]))
            except Exception as e:
                print(f"⚠️  arte do Telegram ({tipo}) não saiu: {e}")
    _grade(arqs, SAIDA / "carrossel-exemplo.jpg", por_linha=len(arqs))
    return itens


def main():
    os.environ["CAMADAS"] = "1"
    SAIDA.mkdir(exist_ok=True)
    fila = garimpar.carregar_fila()
    garimpar.limpar_fila(fila)
    mem = busca_profunda.carregar()
    escolhidas = busca_profunda.escolher_palavras(mem)
    candidatos = garimpar.curar(fila, garimpar.coletar_candidatos(fila, escolhidas=escolhidas, mem=mem))
    candidatos += awin.candidatos(fila, garimpar.ja_usado, julgar=garimpar.julgar_marcas)
    escolhidos = garimpar.selecionar(candidatos, 15,
                                     variedade.contar_pendentes(fila), {})
    esp = [o for o in escolhidos if camadas.especial(o)]
    con = [o for o in escolhidos if not camadas.especial(o) and camadas.conhecido(o)]
    tg = [o for o in escolhidos if variedade.diferenciado(o) and not camadas.especial(o)]
    print("\n===== RODADA COM AS DUAS CAMADAS (nada é gravado) =====")
    for o in esp:
        print(f"⭐ especial  uau {o['uau']:.0f}  R$ {o['preco_fmt']}  {o['nome'][:70]}  | {o.get('gancho')}")
    for o in con:
        print(f"🏷️ conhecido uau {variedade.uau(o):.0f}  R$ {o['preco_fmt']}  {o['nome'][:70]}  | {camadas.motivo_conhecido(o)}")
    for o in tg:
        print(f"📨 só Telegram (uau 7) R$ {o['preco_fmt']}  {o['nome'][:70]}")
    # candidatos que seriam conhecidos mas ficaram de fora (repetidos, família, limite da rodada)
    todos_con = [o for o in candidatos if camadas.conhecido(o)]
    print(f"\nTotal: ⭐ {len(esp)} especiais | 🏷️ {len(con)} conhecidos (de {len(todos_con)} candidatos) | "
          f"📨 {len(tg)} só Telegram")
    _folha(esp, f"⭐ ESPECIAIS desta rodada ({len(esp)}): selo ACHADO DO ZÉ, capa e Reels", "1-especiais.jpg", (150, 100, 10))
    _folha(con, f"🏷️ CONHECIDOS desta rodada ({len(con)}): Telegram, WhatsApp e completam o carrossel",
           "2-conhecidos.jpg", (20, 70, 120))
    fora = [o for o in todos_con if o not in escolhidos][:12]
    _folha(fora, f"Conhecidos que ficaram para a próxima rodada ({len(todos_con) - len(con)})", "3-conhecidos-fora.jpg",
           (110, 110, 110))
    carrossel_exemplo(escolhidos)


if __name__ == "__main__":
    main()
