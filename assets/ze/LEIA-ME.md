# Vídeos do Zé Garimpo (mascote)

## 1. Final dos Reels (`finais/`)
Cada Reels de oferta do Garimpo VIP termina com uma destas vinhetas (3 a 5 s). O robô alterna
entre elas e nunca repete a do post anterior. Para incluir outra, é só colocar o .mp4 em `finais/`.
Para desligar: variável `ZE_NO_FINAL=0`.

As vinhetas têm só a voz do Zé: a música entra depois, contínua no Reels inteiro. O robô escolhe
uma das faixas de `assets/musicas/` (alternando), emenda a faixa nela mesma com transição suave até
o fim do vídeo e abaixa o volume quando o Zé fala. Para incluir outra música, coloque o .mp3 lá.
Desligar: `MUSICA_REELS=0`; volume: `VOLUME_MUSICA` (padrão 0.6).

| Arquivo | Cena |
|---|---|
| finais/fim_link_da_bio.mp4 | aponta para cima e faz joinha — "Corre no link da bio!" |
| finais/fim_tchau_chapeu.mp4 | tira o chapéu — "Amanhã tem mais achado!" |
| finais/fim_garimpo_vip.mp4 | lupa brilhando e joinha — "Esse é garimpo VIP!" |
| finais/fim_carrinho.mp4 | close sorrindo ao lado do carrinho de achados |

## 2. Post do Zé às terças e sextas (`ze_*.mp4`)
O workflow "9 - Post do Zé Garimpo" (todo dia às 13:30, só posta às terças e sextas; mude com `ZE_DIAS`) publica um
destes como Reels no Instagram, story, Facebook e YouTube Shorts. Vídeo que nunca saiu vai primeiro;
depois volta o que está há mais tempo sem sair. O post é apagado com 15 dias, junto das ofertas.
Registro em `data/ze.json`. Para incluir um vídeo novo, coloque `ze_nome.mp4` (8 s, com música) aqui.

| Arquivo | Cena | Música |
|---|---|---|
| ze_rio.mp4 | cai no rio com a bateia cheia | Forró da Alegria |
| ze_tesouro.mp4 | cava caixas e acha um baú | Forró da Alegria (2) |
| ze_detetive.mp4 | reprova produtos ruins com a lupa | Splash and Fanfare (2) |
| ze_vagoneta.mp4 | vagoneta na mina e mergulho | Splash and Fanfare |
| ze_caverna.mp4 | quebra a parede da caverna e acha cristais | Splash and Fanfare (2) |
| ze_chuva_etiquetas.mp4 | chuva de etiquetas no guarda-chuva | Forró da Alegria (2) |
| ze_guarda_chuva.mp4 | chuva de ofertas enchendo a bateia | Forró da Alegria |
| ze_ima.mp4 | ímã gigante puxa os eletrônicos e arrasta o Zé | Splash and Fanfare |
| ze_rede.mp4 | acorda na rede com o despertador | Batida de Início |
| ze_relogio.mp4 | acha um relógio dourado na bateia | Forró da Alegria (2) |
| ze_rio_pulo.mp4 | pula no rio com a bateia de achados | Forró da Alegria |

## 3. Quadro "Você pediu, o Zé achou!" (`src/pedidos.py`)
Todo post do Zé convida: "comenta o produto que você procura". O responder lê esses comentários,
responde "Anotado!" e guarda o pedido em `data/.../pedidos.json`. No garimpo seguinte o robô busca o
produto na Shopee, escolhe o melhor (nota, vendas, comissão) e põe na frente da fila com a legenda
"🙋 VOCÊ PEDIU, O ZÉ ACHOU!" marcando @quem pediu. Quando o post sai, a pessoa recebe o link no direct.
