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
Terças, quintas e sábados às 16h (mude com `ANA_DIAS`; 0 = segunda). Só no Instagram (feed + story).
Vídeo que nunca saiu vai primeiro. Para incluir outro, coloque `ana_nome.mp4` aqui.

## Música
Os vídeos da Ana vêm só com a voz. O robô põe trilha de `assets/ana/musicas/` (mais baixa quando ela fala),
nos Reels de oferta e nos posts próprios. Para trocar ou incluir músicas, é só mexer nessa pasta.

ana_oi_acenando, ana_palmas, ana_olhando_quarto, ana_celular, ana_presente, ana_cafe,
ana_anotando, ana_closet_organizado, ana_skincare
