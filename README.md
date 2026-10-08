# Garimpo VIP — robô de afiliado Shopee

Robô que roda 100% no GitHub Actions e alimenta o Instagram **@garimpovip4**.

| Workflow | O que faz | Quando |
|---|---|---|
| 1 - Garimpo de ofertas | Busca ofertas em 7 nichos, filtra por qualidade, gera a legenda com IA e põe na fila | 06:47 e 14:47 |
| 2 - Postar no Instagram | Pega a melhor oferta da fila, gera a arte (foto) ou o Reels e publica, alternando os formatos | 07:52, 10:52, 12:52, 15:52, 18:52, 20:52 |
| 3 - Responder EU QUERO | Lê os comentários dos posts dos últimos 7 dias e manda o link de afiliado no direct | a cada 15 min |
| 4 - Renovar token | Renova o token do Instagram (vale 60 dias) e atualiza o segredo | toda segunda |

Horários de Brasília. Todos também podem ser disparados em **Actions → Run workflow**.

## Garimpo
`python -m src.garimpar`
- Nichos: eletrônicos, lar, brinquedos, feminino, pet, automotivo e masculino (`src/config.py`).
- Filtros: nota ≥ 4,7, ≥ 100 vendas, comissão ≥ R$ 2, preço ≤ R$ 300, sem palavras proibidas, sem repetir produto em 30 dias.
- Escolhe as 10 melhores por pontuação (comissão, vendas, nota, desconto), no máximo 1 por palavra-chave.
- Legenda pela Groq; se falhar, usa uma legenda padrão e avisa no log.
- Fila em `data/fila.json`. Pendentes vencem em 3 dias.

## Postagem
`python -m src.postar preparar` → `publicar`
- A mídia (`src/imagem.py` foto 1080x1350, `src/reels.py` Reels 1080x1920) é gerada na hora e servida pelo **GitHub Pages**, de onde o Instagram a busca.
- Evita repetir a categoria dos últimos 3 posts.

## Vídeos manuais
Suba um `.mp4` em `videos/` e anote em `videos/lista.txt` o link do produto. O robô busca a oferta, monta o Reels com o vídeo e publica no próximo horário, com prioridade. Instruções em `videos/LEIA-ME.md`.

## Respostas
`python -m src.responder`
- Gatilhos: "eu quero", "quero", "link", "manda".
- Manda o link na resposta privada (direct) e responde publicamente "te mandei no direct".
- Registro em `data/respondidos.json` para não repetir.

## Configuração (uma vez)
1. **Settings → Pages → Source: GitHub Actions**.
2. **Settings → Secrets and variables → Actions**:
   - `SHOPEE_APP_ID`, `SHOPEE_APP_SECRET` — API de Afiliados da Shopee
   - `GROQ_API_KEY` — legendas por IA
   - `IG_ACCESS_TOKEN` — token do Instagram (login do Instagram, conta profissional)
   - `GH_PAT` — token do GitHub com permissão de escrever segredos neste repositório (para a renovação automática do token do Instagram)

Sem o `IG_ACCESS_TOKEN`, a postagem e as respostas ficam em espera, sem dar erro.
