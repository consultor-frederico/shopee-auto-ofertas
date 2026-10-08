# Garimpo VIP — robô de afiliado Shopee

Robô que roda 100% no GitHub Actions e alimenta o Instagram **@garimpovip4**.

| Etapa | O que faz | Status |
|---|---|---|
| 1. Garimpo | Busca ofertas de eletrônicos, lar e brinquedos, filtra por qualidade, gera legenda com IA e a arte do post | ✅ pronto |
| 2. Postagem | Publica a melhor oferta pendente no Instagram | 🔜 |
| 3. Respostas | Lê comentários "EU QUERO" e manda o link de afiliado no direct | 🔜 |

## Como funciona o garimpo

`python -m src.garimpar` — roda 2x por dia (`.github/workflows/garimpo.yml`) ou manualmente em **Actions → Run workflow**.

1. Sorteia palavras-chave do nicho (`src/config.py`), garantindo as 3 categorias.
2. Filtra: nota ≥ 4,7, ≥ 100 vendas, comissão ≥ R$ 2, preço ≤ R$ 300, sem palavras proibidas, sem repetir produto em 30 dias.
3. Pontua (comissão, vendas, nota, desconto) e escolhe as 8 melhores, equilibrando as categorias.
4. Gera título e legenda com a Groq. Se a IA falhar, usa uma legenda padrão e avisa no log.
5. Gera a arte 1080x1350 em `posts/<id>.jpg`.
6. Grava tudo em `data/fila.json` com status `pendente`. Pendentes vencem em 3 dias (preço muda).

Filtros, nicho e ritmo são ajustáveis em `src/config.py`.

## Segredos necessários (Settings → Secrets and variables → Actions)

- `SHOPEE_APP_ID`, `SHOPEE_APP_SECRET` — API de Afiliados da Shopee
- `GROQ_API_KEY` — legendas por IA (opcional; sem ela, usa a legenda padrão)
