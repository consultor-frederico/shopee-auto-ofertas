"""Teste e prévia do Nano Banana (workflow "29 - Testar Nano Banana"). Não posta nada.
Gera o cenário de 3 achados da vitrine e monta a capa de produto com e sem cenário em previa_nano/."""
import json
import pathlib
import time

from . import achados_artes, imagem, nano_banana

SAIDA = pathlib.Path("previa_nano")


def main():
    SAIDA.mkdir(exist_ok=True)
    print("Modelos de imagem que a chave enxerga:", nano_banana.modelos())
    ofertas = [o for o in json.load(open("data/fila.json", encoding="utf-8"))["ofertas"].values()
               if o.get("preco_fmt") and o.get("imagem") and o.get("titulo") and o.get("plataforma") == "shopee"]
    ofertas.sort(key=lambda o: o.get("criado_em", ""), reverse=True)
    vistos, escolhidos = set(), []
    for o in ofertas:   # 3 categorias diferentes
        if o.get("categoria") not in vistos:
            vistos.add(o.get("categoria"))
            escolhidos.append(o)
        if len(escolhidos) == 3:
            break
    for i, oferta in enumerate(escolhidos, 1):
        it = {"titulo": oferta["titulo"], "imagem": oferta["imagem"], "num": oferta.get("categoria")}
        foto = imagem._baixar_foto(it["imagem"])
        t = time.time()
        fundo = nano_banana.gerar(nano_banana.prompt_cenario(it["titulo"]))
        print(f"#{it['num']} {it['titulo']}: {'cenário ok' if fundo else 'sem cenário'} em {time.time() - t:.0f}s")
        achados_artes.capa_produto(oferta, foto, 3, ("aponta", "joia")[i % 2], SAIDA / f"{i}-hoje.jpg")
        if fundo:
            fundo.save(SAIDA / f"{i}-cenario.jpg", quality=90)
            achados_artes.capa_produto(oferta, foto, 3, ("aponta", "joia")[i % 2], SAIDA / f"{i}-com-cenario.jpg",
                                       fundo=fundo)


if __name__ == "__main__":
    main()
