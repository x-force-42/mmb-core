# Plano de imersão temática — MMB

Catálogo das 5 camadas de tematização Mr. Meeseeks propostas pro
`mr-meeseeks-box` (MMB). Cada camada tem escopo, impacto vs. esforço
e status atual. Atualize o status à medida que cada camada migra
entre `pendente`, `em teste` e `consolidado`.

## Princípios editoriais

Sustentam todas as camadas. Quebra qualquer um destes = decisão
explícita, registra aqui.

- **Garagem fala português**, voz de oficina. Rabugenta, sem catchphrase
  do show — ela é da casa, não do universo Mr. Meeseeks.
- **Meeseeks fala inglês**, canônico do show. Catchphrases só nas
  **transições** (spawn, sucesso, falha) e no heartbeat com decay.
- **Conteúdo técnico permanece seco.** Briefing, relatório, cleanup —
  sem tom. O molho fica nas bordas.
- **Decay é a alma do personagem.** Sem decay temporal, vira mascote.
  Com decay, parece ter alma.

## Camadas

### A — Microcopy (impacto alto, custo baixo) — `em teste`

Trocar strings nos momentos de transição. Sem mudança estrutural.

Mudanças aplicadas em `bot.py`:

- Spawn do Meeseeks: `💨 *POOF!* **I'm Mr. Meeseeks, look at me!**`
- Sucesso: `✨ *Can do!* **Missão cumprida em mm:ss.**`
- Falha: `💀 **Existing is pain, Rick.**`
- Pushback da Garagem: `🔧 **Não, Rick. Volta com isso melhor antes
  de eu acordar um Meeseeks.**`
- Status do bot no Discord: `Watching Rick press the button`

Arquivos tocados: `bot.py`.

### B — Heartbeat com decay temporal (impacto alto, custo baixo) — `em teste`

Heartbeat do Meeseeks varia conforme ele "vive demais". Casa com o
lore: quanto mais tempo um Meeseeks existe, mais instável fica.

| Tempo | Frase |
|---|---|
| 0–3min | `🌀 Working on it!` |
| 3–8min | `💪 Caaaaan do!` |
| 8–15min | `😅 Oh boy, this is tricky...` |
| 15–25min | `😬 Existing is becoming pain, Rick...` |
| 25min+ | `💀 Pleeease let me finish...` |

Implementado como função `_meeseeks_decay(seconds)` em `bot.py`.

### D — Visual via Discord embeds (impacto médio-alto, custo médio) — `próximo`

Sair de mensagens texto cru pra embeds com identidade visual.

- Embeds com **cor da barra lateral**: Meeseeks azul, Garagem cinza,
  falha vermelho, dev server amarelo
- **Avatar do bot** (upload no Developer Portal, sem código)
- **Thumbnails opcionais** em sucesso/falha (mini-imagens contextuais)
- **Reactions automáticas** na mensagem original do user
  (🌀 quando spawna, ✅ quando entrega, 💀 quando falha)

Custo estimado: avatar 5min, embeds 1-2h, reactions 30min.

### C — Persona ampliada (impacto médio, custo médio) — `pendente`

Garagem e Meeseeks ganham vocabulário e identidade individualizada.

- Cada **Meeseeks com nome único** (hash do slug, ex.: `Meeseeks-7e3a`)
  ou nomes do show (Karen, Bob). Aparece no status: `🌀 Meeseeks-7e3a
  working...`. Dá identidade ao histórico do canal.
- Garagem com **frase de assinatura recorrente** ("você que confia",
  "lá vamos nós").
- Voice consistente entre system prompts (`skills/*.md`) e UI (`bot.py`).

Custo: 1h prompt + 30min código. Maior carga conceitual que A/B/D.

### E — Interatividade (impacto médio-alto, custo alto) — `pendente`

Tira fricção do copy/paste e adiciona comandos auxiliares.

- **Botões inline no relatório final**: `[✅ Mergear & limpar]`
  `[🗑️ Descartar tudo]` `[🐛 Reportar bug]`. Discord.py via
  `discord.ui.View`. Tira o copy/paste de comandos bash.
- **`/poof <slug>`**: cleanup completo numa tacada (kill dev + remove
  worktree + del branch).
- **`/box-status`**: lista Meeseeks ativos, commits ainda não-mergeados,
  estado do dev server.
- **`/spawn-another`**: easter egg referenciando "Mr. Meeseeks asking
  for help". Pode ficar inativo agora ("Coming soon: task decomposition")
  como semente futura.

Custo: cada comando ~1h. Cresce escopo.

## Ordem sugerida

1. A — microcopy (feito)
2. B — heartbeat com decay (feito)
3. D — visual / embeds
4. E — interatividade (depois de E você reduz a quantidade de bash
   manual que sobra na UX)
5. C — persona ampliada (quando o canal tiver volume suficiente de
   Meeseeks pra valer a pena nomear cada um)
