# 🔎 Vídeos da Busca do Zé

Coloque aqui os vídeos do Flow da Busca do Zé com nome `busca_*.mp4` (ex.: `busca_chamada.mp4`,
`busca_pedidos.mp4`, `busca_achei.mp4`), na vertical (9:16).

- A cada 15 dias (variável `BUSCA_INTERVALO_DIAS`), o workflow "18 - Reels da Busca do Zé" posta um deles
  no Instagram (Reels + story), em rodízio: primeiro os que nunca saíram, depois o que está há mais tempo sem sair.
- O robô grava por cima do vídeo, do começo ao fim, a faixa "BUSCA DO ZÉ" e o quadro
  "TÁ PROCURANDO ALGUMA COISA? Comenta aqui que o Zé acha pra você" — não precisa escrever nada no vídeo.
- Quando sai um Reels novo da Busca, o anterior é apagado. O post fixo (a foto) não é mexido.
- A legenda leva #BuscaDoZe, então quem comentar recebe os achados no direct (src/busca_ze.py).
- Para conferir a faixa num vídeo antes: `python -m src.busca_reels previa caminho/do/video.mp4`.
