# Garimpo VIP — robô de afiliado Shopee

Robô que roda 100% no GitHub Actions e alimenta duas contas do Instagram:

| Perfil (`PERFIL`) | Conta | Nichos | Identidade |
|---|---|---|---|
| `garimpo` (padrão) | **@garimpovip4** | eletrônicos, casa, brinquedos, pet, automotivo, masculino | marrom e dourado, `assets/logo.png`, Telegram |
| `ana` | **@ananovoachados** | beleza, cabelo, moda, autocuidado, casa fofa — público feminino e LGBTQIA+ | rosa e roxo com listra arco-íris, `assets/ana/logo.png` |

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
- Filtro em dois níveis (calibrado com amostra de 7.161 produtos):
  - 🏅 **Ouro** (Instagram): ≥ 1.000 vendas, comissão ≥ R$ 8 e ≥ 10%, "fator uau" da IA ≥ 7.
  - 🥈 **Prata** (Telegram): ≥ 500 vendas, comissão ≥ R$ 5 e ≥ 8%, "fator uau" ≥ 6.
  - Sempre: nota ≥ 4,7, preço ≤ R$ 300, sem palavras proibidas.
- Anti-repetição: descarta nomes muito parecidos ou mesma loja + mesmo preço; não repete no Instagram em 30 dias (Telegram: 14).
- Busca 2 páginas dos mais vendidos + a página de maior comissão de cada palavra-chave.
- Escolhe as 15 melhores por pontuação (comissão, vendas, nota, desconto), no máximo 1 por palavra-chave.
- Legenda pela Groq; se falhar, usa uma legenda padrão e avisa no log.
- Fila em `data/fila.json`. Pendentes vencem em 3 dias.

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

## Respostas
`python -m src.responder`
- Gatilhos: "eu quero", "quero", "link", "manda".
- Manda o link na resposta privada (direct) e responde publicamente "te mandei no direct".
- Registro em `data/respondidos.json` para não repetir.
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
