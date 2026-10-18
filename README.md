# Garimpo VIP — robô de afiliado Shopee

Robô que roda 100% no GitHub Actions e alimenta duas contas do Instagram:

| Perfil (`PERFIL`) | Conta | Nichos | Identidade |
|---|---|---|---|
| `garimpo` (padrão) | **@garimpovip4** | eletrônicos, casa, brinquedos, pet, automotivo, masculino | marrom e dourado, `assets/logo.png`, Telegram |
| `ana` | **@ananovoachados** | beleza, cabelo, moda, autocuidado, casa fofa — público feminino e LGBTQIA+ | azul-noite e verde-menta, moldura em arco, `src/layout_ana.py` e `assets/ana/` |

Cada conta tem sua fila e seu registro de respostas (`data/` e `data/ana/`), seu token (`IG_ACCESS_TOKEN` e `IG_ACCESS_TOKEN_ANA`) e horários próprios no `agenda.yml`. Os workflows 1, 2 e 4 têm a opção **perfil** ao rodar manualmente; o 3 responde as duas contas de uma vez.

| Workflow | O que faz | Quando |
|---|---|---|
| 1 - Garimpo de ofertas | Busca 15 ofertas em 7 nichos, filtra por qualidade, gera a legenda com IA e põe na fila | 06:47, 11:47 e 17:47 |
| 2 - Postar no Instagram | Pega a melhor oferta da fila, gera a arte (foto) ou o Reels e publica, alternando os formatos | 07:52, 10:52, 12:52, 15:52, 18:52, 20:52 |
| 3 - Responder EU QUERO | Lê os comentários dos posts dos últimos 7 dias e manda o link de afiliado no direct | a cada 15 min |
| 4 - Renovar token | Renova o token do Instagram (vale 60 dias) e atualiza o segredo | toda segunda |
| 5 - Testar Telegram | Mensagem de teste no canal | manual |
| 6 - Ofertas no Telegram | 2 ofertas por hora no canal | 08:22–22:22 |
| 7 - Campanhas e cupons | Publica campanhas novas da Shopee no canal | 00:13, 08:13, 12:13, 18:13 |
| 8 - Chamada do Telegram | Post no Instagram chamando para o canal | terça e sexta, 19:37 |

Horários de Brasília. Todos também podem ser disparados em **Actions → Run workflow**.

## Garimpo
`python -m src.garimpar`
- Nichos: eletrônicos, lar, brinquedos, feminino, pet, automotivo e masculino (`src/config.py`).
- Filtro em dois níveis (recalibrado em 09/10/2026 com 21.858 produtos):
  - 🏅 **Ouro** (Instagram): ≥ 500 vendas, comissão ≥ R$ 6 e ≥ 8%, "fator uau" da IA ≥ 7.
  - 🥈 **Prata** (Telegram): ≥ 500 vendas, comissão ≥ R$ 5 e ≥ 8%, "fator uau" ≥ 6.
  - Sempre: nota ≥ 4,7, preço ≤ R$ 300, sem palavras proibidas.
- Anti-repetição: descarta nomes muito parecidos ou mesma loja + mesmo preço; não repete no Instagram em 30 dias (Telegram: 14).
- Sorteia 24 palavras-chave por garimpo, a mesma quantidade em cada categoria, e busca 2 páginas dos mais vendidos + a página de maior comissão de cada uma.
- No máximo 2 produtos do mesmo tipo por garimpo (ex.: dois espelhos).
- Escolhe as 15 melhores por pontuação (comissão, vendas, nota, desconto), no máximo 1 por palavra-chave.
- Legenda pela Groq; se falhar, usa uma legenda padrão e avisa no log.
- Fila em `data/fila.json`. Pendentes vencem em 3 dias.

## AliExpress
`src/aliexpress.py` — API de Afiliados (app **Garimpo VIP**, AppKey 552254). Em cada garimpo, cada palavra-chave também é buscada na AliExpress e as ofertas entram na mesma curadoria (uau, ouro/prata).
- Só produtos com entrega em até 7 dias para o Brasil, ≥ 95% de avaliações positivas e comissão ≥ R$ 5 (prata) / R$ 6 (ouro). A AliExpress paga 7% padrão, então o mínimo em % lá é 7%.
- Na arte aparece o selo "OFERTA ALIEXPRESS" e "% aprovação" no lugar das estrelas.
- Segredos: `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET`, `ALIEXPRESS_TRACKING_ID`. Teste em **Actions → 10 - Testar AliExpress**.

## Shark Ninja (Awin)
`src/awin.py` — programa **Shark-Ninja BR** (rede Awin, publisher 3120546, CPA 8%, cookie de 30 dias). Diferente da Shopee e da AliExpress, não há busca por palavra-chave, nem vendas ou nota: o robô lê o **feed de produtos** da marca (CSV com vírgula, gzip) e usa o link de afiliado que já vem pronto em cada produto (`aw_deep_link`).
- **Segredo `AWIN_FEED_URL`:** URL do feed (Awin → Ferramentas → Crie um Feed → Shark-Ninja BR). Ela contém a chave da Awin: nunca vai para log nem para o chat. **Ligada por padrão** quando o segredo existe. **Para desligar:** crie a variável `AWIN_ATIVO` com valor `0` em Settings → Secrets and variables → Actions → *Variables*.
- **Cada conta no seu nicho:** Garimpo VIP = casa e cozinha (aspiradores, robôs, air fryer, liquidificador…, categoria `lar`); Ana Novo Achados = secadores e modeladores de cabelo (`cabelo`). Filtro: peça de reposição, produto sem estoque, sem foto ou sem link ficam de fora.
- **Regras próprias:** sem teto de preço, sem corte por vendas/nota, sem nota de "uau" da IA (marca oficial). As artes, o Telegram e o WhatsApp mostram "Loja oficial Shark Ninja" no lugar de nota e vendas. Ordem de entrada: maior desconto e maior comissão.
- **Frequência (`src/config.py`):** até 3 produtos novos por rodada de garimpo, **1 por dia no Instagram de cada conta**, até 3 por dia no Telegram (1 por rodada). Produto já usado não volta por 14 dias (Telegram) e 30 dias (Instagram), então o catálogo roda sozinho.
- **Preço honesto:** antes de postar, `awin.conferir()` baixa o feed de novo; produto que saiu do feed ou ficou sem estoque é descartado e preço que subiu mais de 15% também.
- **Termos do programa:** permite pessoa física, influenciadores e grupos de oferta; **não permite busca paga (Google Ads)**; cupom que não seja da marca não gera comissão.
- **Fotos:** o feed só traz miniatura (292 px); a loja é VTEX, então `imagem._baixar_foto` pede a foto original (1500 px) e usa a miniatura só se falhar.
- **Voltagem:** o mesmo produto vem em 110V e 220V; fica uma versão por produto (Bivolt, depois 110V, depois 220V) e o aviso do preço diz para conferir a voltagem.
- Teste: **Actions → 13 - Testar Shark Ninja (Awin)** (lê o feed, mostra o que o robô entendeu e faz uma prévia de legenda e arte de 2 produtos por conta; não posta nada). O resultado aparece nas anotações do job.

## Postagem
`python -m src.postar preparar` → `publicar`
- A mídia (`src/imagem.py` foto 1080x1350, `src/reels.py` Reels 1080x1920) é gerada na hora e servida pelo **GitHub Pages**, de onde o Instagram a busca.
- Evita repetir a categoria dos últimos 3 posts.

## Vídeos manuais
Suba um `.mp4` em `videos/` e anote em `videos/lista.txt` o link do produto. O robô busca a oferta, monta o Reels com o vídeo e publica no próximo horário, com prioridade. Instruções em `videos/LEIA-ME.md`.

## Telegram
Ritmo próprio, mais intenso que o Instagram: **2 ofertas por hora, das 8h às 22h** (workflow 6, ~30/dia), com a arte, o preço e um botão com o link direto. As ofertas publicadas no Instagram também vão para o canal (sem repetir). Segredos: `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`. Teste em **Actions → 5 - Testar Telegram**.

## Campanhas e cupons (workflow 7)
O robô consulta a API de campanhas da Shopee 4x por dia (00:13, 08:13, 12:13, 18:13). As ~30 páginas fixas de categoria são ignoradas; quando aparece campanha nova (cupons, 11.11, Black Friday…), publica no Telegram com botão e o link de afiliado, e avisa de novo nas últimas 12 horas. Registro em `data/campanhas.json`.

## Chamada para o Telegram (workflow 8)
Terça e sexta às 19:37, um post no Instagram com arte própria chamando para o canal (link na bio). Alterna 3 artes e 3 legendas.

## Facebook, stories e limpeza
- **Página do Facebook (Garimpo VIP):** cada oferta do Instagram também é publicada na página (foto ou vídeo). Quem comenta "quero" lá recebe o link pelo **Messenger**. Segredos: `FB_PAGE_ID`, `FB_PAGE_TOKEN` (token de página, não expira). Teste em **Actions → 11 - Testar Facebook**.
- **Stories:** cada post do feed vai também para o story (arte vertical ou o próprio Reels). A API não permite adesivo de link.
- **Limpeza (workflow 12): desligada.** Os posts antigos ficam no ar, porque a legenda já avisa o dia e a hora em que o preço foi conferido. Dá para rodar à mão no Actions, se um dia precisar.

## Respostas
`python -m src.responder`
- Gatilhos: "eu quero", "quero", "link", "manda".
- Manda o link na resposta privada (direct) e responde publicamente "te mandei no direct".
- Registro em `data/respondidos.json` para não repetir.
- **Respostas humanas (17/10/2026):** o Zé e a Ana respondem cada vez de um jeito (várias versões de direct e de comentário público, às vezes chamando a pessoa pelo @). O robô também espera de 1 a 6 minutos antes de responder cada comentário (tempo fixo por comentário; o comentário novo fica para a rodada seguinte). Para mudar: variável `RESPOSTA_ESPERA_MAX_MIN` (0 desliga). Os começos das mensagens do robô precisam estar em `MARCAS_ROBO` (`src/busca_ze.py`), senão a Busca do Zé acha que foi o Fred que escreveu.
- **Legendas dos posts próprios do Zé e da Ana:** abrem com gancho e pedem para seguir; nos 45 dias antes da Black Friday entra a contagem regressiva ("faltam N dias"), calculada sozinha (`ze.dias_para_black_friday`).
- **Instantâneo:** o webhook do Instagram chama o Cloudflare Worker (`webhook/worker.js`), que dispara esta rotina na hora (~30–60 s). A cada 15 min ela também roda como reserva.

## Configuração (uma vez)
1. **Settings → Pages → Source: GitHub Actions**.
2. **Settings → Secrets and variables → Actions**:
   - `SHOPEE_APP_ID`, `SHOPEE_APP_SECRET` — API de Afiliados da Shopee
   - `GROQ_API_KEY` — legendas por IA
   - `IG_ACCESS_TOKEN` — token do Instagram (login do Instagram, conta profissional)
   - `IG_ACCESS_TOKEN_ANA` — token da @ananovoachados
   - `GH_PAT` — token do GitHub com permissão de escrever segredos neste repositório (para a renovação automática do token do Instagram)

Sem o `IG_ACCESS_TOKEN`, a postagem e as respostas ficam em espera, sem dar erro.

## 🛍️ Carrossel de Achados (workflow 24)

Os posts do feed agora são **carrosséis de 3–5 produtos**, sempre abrindo com um **vídeo do Zé (Garimpo) ou da Ana** e fechando com a chamada "QUERO + número".
Quem comenta `QUERO 2` recebe o link do 2º; só `QUERO` recebe a lista (registro em `data/<perfil>/top.json`).

- Código: `src/achados.py` (fluxo) e `src/achados_artes.py` (artes). A cada carrossel muda o estilo (3 de produto, 2–3 de slide final, 3 títulos no vídeo, topo/rodapé alternando); contador em `data/<perfil>/achados.json`.
- Posts de produto único (`postar.yml`) só saem para "Você pediu, o Zé achou" e vídeos manuais (`SO_CARROSSEL=0` volta ao modo antigo).
- Variáveis: `ACHADOS_QTD` (3–5, padrão 4), `ACHADOS_MINIMO` (padrão 3), `ACHADOS_VARIANTE` (força um estilo, p/ prévia), `ZE_SEMPRE_NO_INICIO` (padrão 1: todo Reels abre com o personagem), `ANA_DIAS` (padrão `0,1,2,3,4,5,6`: vídeo próprio da Ana todo dia).
- Horários (`agenda.yml`): Garimpo 07:45, 12:45, 18:45; Ana 09:15, 14:30, 19:15.
- Prévia local: `python -m src.achados previa` (gera em `data/relatorios/achados/`).
