# Task A1 — Aquário mono-projeto

## ID
A1

## Trilha
A — Presença

## Status
🎯 pronto pra delegar

## Intenção

Dar vida visual ao MMB. Hoje o sistema é "auditável retrospectivamente"
via Datasette, mas você não **vê** os Meeseeks vivendo. O aquário
(serviço externo desenvolvido por outro time) renderiza cada Meeseeks
como criatura na tela, com saúde decaindo no tempo, eventos discretos
e morte feliz/derrotada.

A integração é **one-way**: MMB conecta num WebSocket do aquário e
empurra JSON. Sem ack, sem polling. Esta task faz essa ponte para
um único MMB rodando contra um único projeto (mono). Multi-projeto
fica pra A3 quando B1 estiver pronto.

## Escopo

### Dentro
- Cliente WebSocket reconnecting em `aquario/client.py`, com fila
  in-memory (ring buffer) pra não perder events durante reconnect.
- Mapeamento do ciclo de vida do Meeseeks (já existente em
  `bot.py`/`meeseeks.py`) para os 3 tipos de mensagem do aquário:
  `snapshot`, `state`, `event`.
- Hook no `bot.py` que emite eventos nos pontos canônicos:
  - `event born` quando o Meeseeks é spawnado (após Garagem ok)
  - `state` periódicos durante o decay (a cada 5s, casado com
    o heartbeat já existente)
  - `event freaking_out` quando o decay cruza o limite de 15min
  - `event died_happy` em sucesso
  - `event died_defeated` em `meeseeks_failure`
- Config via `.env`: `AQUARIUM_WS_URL`, `AQUARIUM_TOKEN`,
  `AQUARIUM_ENABLED` (default `false` pra não quebrar dev local).
- Heartbeat (ping a cada 30s, drop após 10s sem pong) com reconnect
  com backoff exponencial 1s→2s→4s→8s→16s, max 30s.
- Testes unitários sobre o mapeamento de fase → mensagem (sem
  conexão real).

### Fora
- Campo `project` no payload — fica mockado pro slug do
  `TARGET_PROJECT_PATH` por enquanto. A3 troca por valor real.
- Identidade visual dos Meeseeks (`name` "Meeseeks-XXXX") — Camada C
  é A2.
- O serviço aquário em si. Não conhecemos detalhes do servidor
  além do protocolo recebido.
- `event recovered` — não há fonte natural no MMB hoje. Fica não
  utilizado (a decisão é do Rick, vide "Decisões em aberto").

## Critério de pronto

1. Variável `AQUARIUM_ENABLED=true` no `.env` faz o bot conectar
   no `AQUARIUM_WS_URL` durante `on_ready`. Falha de conexão NÃO
   derruba o bot (só loga warning + continua sem aquário).
2. Spawn de Meeseeks emite `event born` com `id`, `health=1.0`,
   `isFreakingOut=false`, `name` (slug), `task` (task_raw).
3. Durante o run, `state` é emitido a cada 5s com health derivada
   do decay temporal. Health vai de 1.0 (recém-nascido) até ~0.1
   (em pain).
4. Cruzar o limite de "freaking_out" (entre 15-25min) emite
   `event freaking_out` UMA vez (não repete).
5. Final do run emite `event died_happy` (success) ou
   `event died_defeated` (qualquer outra fase terminal). Sai do
   pool de "vivos".
6. Reconnect: derruba o WebSocket no meio de um run, verifica que
   os events bufferados são enviados após reconnect, e que o
   próximo snapshot inclui o Meeseeks vivo.
7. `pytest tests/unit/test_aquario_*.py` verde, com testes que
   exercitam o mapeamento sem precisar de servidor real.
8. Bot continua funcional com `AQUARIUM_ENABLED=false` (default).
9. **Conexão real validada**: combinar com o Rick uma URL de
   teste do aquário e rodar um `/meeseeks` smoke confirmando que
   o Meeseeks aparece, decai, e morre na tela.

## Contexto técnico

### Arquivos relevantes
- `bot.py` — pontos de emissão. Olhe `_send_garagem_*`,
  `_send_meeseeks_*`, `_send_success`, `_send_*_failure`. Cada um
  é um ponto de "morte".
- `bot.py:_heartbeat` — função que reedita a mensagem do Discord
  com decay. Reaproveite a curva pra calcular health.
- `embeds.py:_meeseeks_decay` — função pura que retorna a frase
  do decay por tempo (5 estágios). **Use a mesma curva** pra
  derivar health.
- `pipeline.py` — `PipelineResult` com `phase` (literal das 6
  fases terminais). Use pra decidir tipo de morte.
- `garagem.py`/`meeseeks.py` — onde a Garagem/Meeseeks roda. Não
  precisa tocar a princípio.
- `config.py` — onde adicionar os 3 envs novos.

### Padrões do projeto
- Async/await em tudo que toca IO. Use `websockets` (já é deps
  comum) ou `aiohttp`.
- Falha externa não derruba o bot — sempre `try/except` com
  `print("[warn] ...")` e continua.
- Dataclasses pra modelos de mensagem.
- Testes em `tests/unit/test_aquario_*.py` ou subpasta dedicada.

### Spec do aquário (resumida do briefing recebido)

WebSocket one-way (push do MMB). 3 tipos de mensagem JSON:

```json
// snapshot — enviado no connect
{
  "type": "snapshot",
  "meeseeks": [
    {"id": "...", "health": 0.7, "isFreakingOut": false,
     "name": "...", "task": "..."}
  ]
}

// state — update de health de um id existente
{"type": "state", "id": "...", "health": 0.4}

// event — transição discreta
{"type": "event", "kind": "born",
 "id": "...", "name": "...", "task": "..."}

{"type": "event", "kind": "died_happy", "id": "..."}
{"type": "event", "kind": "died_defeated", "id": "..."}
{"type": "event", "kind": "freaking_out", "id": "..."}
{"type": "event", "kind": "recovered", "id": "..."}   // não usaremos
```

Mapeamento de decay → health (esboço, calibrar):

| Tempo do Meeseeks | Frase decay | Health proposta |
|---|---|---|
| 0-3min | Working on it! | 1.0 → 0.85 |
| 3-8min | Caaaaan do! | 0.85 → 0.65 |
| 8-15min | Oh boy, this is tricky | 0.65 → 0.40 |
| 15-25min | Existing is becoming pain | 0.40 → 0.15 (freaking_out!) |
| 25min+ | Pleeease let me finish | 0.15 → 0.05 |

## Implementação sugerida

Estrutura:

```
aquario/
├── __init__.py
├── client.py        # WebSocket client com reconnect + ring buffer
├── messages.py      # dataclasses + serializer (Snapshot, State, Event)
└── lifecycle.py     # converte phase/elapsed → mensagem
```

`client.py`: classe `AquarioClient` com `start()`, `stop()`,
`emit(message)`. `emit` enfileira; uma task asyncio drena a fila
no socket. Reconnect transparente. Heartbeat via `ping_interval`.

`lifecycle.py`: funções puras testáveis. `health_from_elapsed(s)`,
`event_for_phase(phase) -> Optional[Event]`, etc.

Hook em `bot.py`: instancia o cliente em `on_ready` (igual ao
`_logger`). Cada `_send_*` chama `_aquario.emit(...)` (best-effort,
nunca raises).

Para `state` periódico: aproveite o `_heartbeat` async task que já
roda durante o run. Em vez de só editar o Discord, também emite
state pro aquário.

## Testes a adicionar

`tests/unit/test_aquario_lifecycle.py`:
- `health_from_elapsed(0)` ≈ 1.0
- `health_from_elapsed(900)` ≈ 0.4 (15min)
- `health_from_elapsed(1800)` ≈ 0.05 (30min)
- `event_for_phase("success")` → `died_happy`
- `event_for_phase("meeseeks_failure")` → `died_defeated`
- `event_for_phase("garagem_pushback")` → `None` (Meeseeks nem
  spawnou)

`tests/unit/test_aquario_client.py`:
- Mock do WebSocket. `emit` enfileira mensagens.
- Disconnect dispara reconnect com backoff (verifica delays).
- Ring buffer descarta mais antigo quando full.
- `stop()` drena e fecha graciosamente.

## Decisões em aberto

1. **`event recovered`** — não há fonte natural no MMB. Recomendo
   deixar fora desta task. Se quiser instrumentar, é evolução
   futura (ex.: detectar que `npm test` passou após uma falha
   intermediária no Meeseeks). Confirme com o Rick.
2. **Tamanho do ring buffer** — 1000 mensagens. Suficiente pra
   absorver disconnect de minutos.
3. **`AQUARIUM_ENABLED=false` default** — pra não exigir aquário
   ativo durante dev local nem nos testes E2E (eles não devem
   depender da conexão externa).
4. **Library** — sugiro `websockets>=12` (mantida, async-nativa,
   simples). Adicione ao `requirements.txt` (ou onde estiver hoje).
   Verifique antes se já há outra lib WS no projeto.
5. **Conexão real** — você não vai conseguir testar end-to-end sem
   o serviço do aquário rodando em algum lugar acessível. Combine
   com o Rick um endpoint de staging. Sem isso o critério #9 não
   fecha.

## Dependências
- Bloqueia: A3 (aquário multi-projeto depende deste primeiro).
- Bloqueado por: nada. Mas C1 (retry transiente) deveria fechar
  antes pra reduzir flakes no smoke.

## Conflito potencial com
**B1**. Ambos tocam `bot.py` em pontos relacionados (handlers,
`on_ready`, gravação de eventos). Não rodar em paralelo com B1 —
ver matriz em `INDEX.md`.

## Estimativa
~2-3 dias. Cliente WS + reconnect bem feito é ~1d. Mapeamento +
hooks no bot ~0.5d. Testes ~0.5d. Smoke real (depende do aquário
estar acessível) ~0.5d.
