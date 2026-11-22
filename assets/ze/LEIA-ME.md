# Vídeos do Zé Garimpo (mascote)

## 0. Começo dos Reels (`inicios/`)
Cada Reels de oferta abre com 1,8 s do Zé, sem fala (tirando o chapéu, soltando fogos, abrindo a caixa
mágica...), para prender quem está rolando o feed. O robô alterna e não repete o do post anterior.
Para incluir outro, coloque o .mp4 curtinho (sem fala) em `inicios/`. Desligar: `ZE_NO_INICIO=0`.

## 1. Final dos Reels (`finais/`)
Cada Reels de oferta do Garimpo VIP termina com uma destas vinhetas (3 a 5 s). O robô alterna
entre elas e nunca repete a do post anterior. Para incluir outra, é só colocar o .mp4 em `finais/`.
Para desligar: variável `ZE_NO_FINAL=0`.

As vinhetas têm só a voz do Zé: a música entra depois, contínua no Reels inteiro. O robô monta
uma sequência com faixas diferentes de `assets/musicas/` (ordem sorteada, sem abrir com a mesma do
Reels anterior), emendadas com transição suave, e abaixa o volume quando o Zé fala. Quanto mais
.mp3 na pasta, mais variado fica: para incluir outra música, é só colocar o arquivo lá.
Desligar: `MUSICA_REELS=0`; volume: `VOLUME_MUSICA` (padrão 0.6).

| Arquivo | Cena |
|---|---|
| finais/fim_link_da_bio.mp4 | aponta para cima e faz joinha — "Corre no link da bio!" |
| finais/fim_tchau_chapeu.mp4 | tira o chapéu — "Amanhã tem mais achado!" |
| finais/fim_garimpo_vip.mp4 | lupa brilhando e joinha — "Esse é garimpo VIP!" |
| finais/fim_carrinho.mp4 | close sorrindo ao lado do carrinho de achados |

## 2. Post do Zé todo dia (`ze_*.mp4`)
O workflow "9 - Post do Zé Garimpo" (todo dia às 13:30, só posta às segundas, quartas, sextas e domingos; mude com `ZE_DIAS`) publica um
destes como Reels no Instagram, story, Facebook e YouTube Shorts. Vídeo que nunca saiu vai primeiro;
depois volta o que está há mais tempo sem sair. O post é apagado com 15 dias, junto das ofertas.
Registro em `data/ze.json`. Para incluir um vídeo novo, coloque `ze_nome.mp4` (8 s, com música) aqui.
Vídeo novo sem trilha própria: nomeie `ze_nome_semtrilha.mp4` e o robô põe a música. Com trilha própria: `ze_nome_comtrilha.mp4` (o robô não põe música). Os antigos já têm música gravada e ficam como estão.

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
| ze_churrasco.mp4 | acha um celular no espeto do churrasco | Forró da Alegria |
| ze_bateia_brilho.mp4 | sorri e pisca com a bateia cheia de achados | Happy Tails |
| ze_presente.mp4 | traz um presente embrulhado que brilha | Travelling Light |
| ze_fogos.mp4 | solta um sinalizador que vira fogos de sacolinhas | Splash and Fanfare (2) |
| ze_joinha.mp4 | aponta para cima e faz joinha | Toys Are Us |
| ze_chapeu.mp4 | tira o chapéu entre brilhos dourados | Forró da Alegria (2) |
| ze_balanca.mp4 | pesa moedas na balança e morde uma | Batida de Início |
| ze_caixa_magica.mp4 | abre uma caixa mágica e saem produtos voando | Toys Are Us |
| ze_balao-de-preco_semtrilha.mp4 | estoura o balão do preço que incha antes da Black Friday | (robô põe) |
| ze_salario_semtrilha.mp4 | salário dia 5 vs dia 6: as moedas voam da bateia | (robô põe) |
| ze_olhadinha_semtrilha.mp4 | "só vou dar uma olhadinha" e sai cheio de caixas | (robô põe) |
| ze_rastreio_semtrilha.mp4 | espera a encomenda de binóculo até a caixa cair na cabeça | (robô põe) |
| ze_escondido_semtrilha.mp4 | esconde a encomenda atrás das pedras | (robô põe) |
| ze_lista-de-desejos_semtrilha.mp4 | a lista de desejos rola morro abaixo | (robô põe) |
| ze_carrinho-esquecido_semtrilha.mp4 | desenterra um carrinho de compras esquecido | (robô põe) |
| ze_pela-foto_semtrilha.mp4 | puxa uma corda enorme e sai uma caixinha do tamanho de um dedal (texto já gravado pelo Flow) | (robô põe) |
| ze_jumento_semtrilha.mp4 | o jumento senta e não anda mais: "o limite chegou" | (robô põe) |
| ze_tudo-junto_semtrilha.mp4 | a torre de caixas desaba em cima dele | (robô põe) |
| ze_eco_semtrilha.mp4 | grita "achei baratinho!" no alto do morro | (robô põe) |
| ze_ajudante_semtrilha.mp4 | o cachorro caramelo cava e traz um chinelo velho | (robô põe) |
| ze_detector_semtrilha.mp4 | o detector apita para tudo, até para a fivela do cinto | (robô põe) |
| ze_madrugada_semtrilha.mp4 | 3 da manhã, olho arregalado: "só mais um e eu durmo" (texto já gravado pelo Flow) | (robô põe) |
| ze_onde-comprou_semtrilha.mp4 | os bichos da vila perguntam "onde você comprou?" | (robô põe) |
| ze_pescaria_semtrilha.mp4 | pesca bota, bota... e uma caixinha dourada | (robô põe) |
| ze_grupo-familia_semtrilha.mp4 | manda um achado no grupo da família e chovem balões de conversa | (robô põe) |
| ze_amigo-secreto_semtrilha.mp4 | tira no amigo secreto alguém que nem conhece (só nov/dez) | (robô põe) |
| ze_treno_semtrilha.mp4 | desce o morro de gorro de Natal na bateia cheia de presentes (só nov/dez) | (robô põe) |

| ze_tatu_chegada_semtrilha.mp4 | estreia do Tatu Carão: sai do buraco na mina, "Vim pra Black Friday!" (19 s, só nov/dez) | trilha do Tatu |
| ze_tatu_prazer_semtrilha.mp4 | Tatu se apresenta no caixote e a pistola de etiquetas dispara no rosto dele | trilha do Tatu |
| ze_tatu_cronometro_semtrilha.mp4 | "acaba em 10 segundos!" e volta o relógio escondido | trilha do Tatu |
| ze_tatu_espelho_semtrilha.mp4 | ensaia no espelho "últimas unidades" e o espelho racha (fala já legendada pelo Flow) | trilha do Tatu |
| ze_tatu_leve-dois_semtrilha.mp4 | "leve 2, pague 3!" e a barraca quebra | trilha do Tatu |
| ze_tatu_letrinha_semtrilha.mp4 | a letrinha miúda desenrola e ele tropeça | trilha do Tatu |
| ze_tatu_bonus_semtrilha.mp4 | o "bônus exclusivo" é uma caixa vazia com mariposa | trilha do Tatu |

Vídeos do Tatu (`ze_tatu_*`): o Tatu Carão é o arqui-inimigo do Zé, e o texto de tela e o 1º comentário dizem isso. Arte própria (`src/tatu_arte.py`: etiqueta amarela, moldura roxa, selo) e legenda com a ficha dele (`ze.legenda_tatu`). música só de `assets/musicas_tatu/`, tela cheia (sem produtos), não abrem carrossel.

Vídeos de temporada: `TEMPORADA` em `src/ze.py` diz em que meses cada um pode sair (fora disso não entra no rodízio).

### Músicas (`assets/musicas/`)
22/11/2026: entraram 6 trilhas do Google Flow Music, cada uma cortada em 4 trechos de 20 s (`_1` a `_4`):
viola_garimpeiro, corrida_do_ouro, faroeste, frevo, samba_rock, carimbo. Tocam nos Reels de oferta e nos do Zé.
Músicas do Tatu Carão NÃO vão aqui: ficam em `assets/musicas_tatu/` (o robô não usa essa pasta nos Reels de oferta).

Vídeo novo sai primeiro como Reels do Zé, na ordem de `ordem.txt`; só depois de estrear ele pode abrir carrossel.

## 3. Quadro "Você pediu, o Zé achou!" (`src/pedidos.py`)
Todo post do Zé convida: "comenta o produto que você procura". O responder lê esses comentários,
responde "Anotado!" e guarda o pedido em `data/.../pedidos.json`. No garimpo seguinte o robô busca o
produto na Shopee, escolhe o melhor (nota, vendas, comissão) e põe na frente da fila com a legenda
"🙋 VOCÊ PEDIU, O ZÉ ACHOU!" marcando @quem pediu. Quando o post sai, a pessoa recebe o link no direct.
