# Vídeos da Ana (Ana Novo Achados)

Feitos no Google Flow (9:16, 8 s, com a voz dela). Só saem na @ananovoachados.
Funciona igual ao Zé no Garimpo VIP (código em `src/ze.py`, que lê esta pasta quando `PERFIL=ana`).
Registro do rodízio em `data/ana/ze.json`.

## 1. Reels de oferta (rodízio de 3)
Dois Reels terminam com a Ana se despedindo (`finais/`) e o terceiro abre com 1,8 s dela, sem som (`inicios/`).

| Arquivo | Cena |
|---|---|
| inicios/ini_oi_acenando.mp4 | acena para a câmera |
| inicios/ini_palmas.mp4 | bate palmas e sorri |
| inicios/ini_olhando_quarto.mp4 | olha em volta no quarto |
| finais/fim_apontando.mp4 | aponta para o lado e fala (3,6 s) |
| finais/fim_tchau_pijama.mp4 | de pijama na cama, se despedindo (7 s) |

## 2. Post próprio da Ana (`ana_*.mp4`)
1 por semana, às quintas às 16h (mude com `ANA_DIAS`; 0 = segunda). Só no Instagram (feed + story).
Ordem sorteada: primeiro os que nunca saíram; depois, entre a metade que está há mais tempo sem sair.
Para incluir outro, coloque `ana_nome.mp4` aqui. Vídeo com "busca" no nome (ana_busca_chamada.mp4)
sai com a faixa "Busca da Ana" por cima e legenda #BuscaDaAna.

## 3. Busca da Ana (`busca/`)
Igual à Busca do Zé: quem comenta num post com #BuscaDaAna (ou pede outro produto num Reels de oferta,
ou manda no direct) recebe 3 achados no direct. `busca/busca_fixo.mp4` é o Reels para fixar no perfil:
publicado pelo workflow "18 - Reels da Busca" com perfil = ana (não é apagado e não entra em rodízio).

## Música
Os vídeos da Ana vêm só com a voz. O robô põe trilha de `assets/ana/musicas/` (músicas só dela, nunca as do
Garimpo VIP), como música ambiente bem baixinha (VOLUME_MUSICA 0.35), mais baixa ainda quando ela fala.
