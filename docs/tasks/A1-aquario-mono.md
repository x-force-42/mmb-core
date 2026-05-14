# Task A1 — Aquário mono-projeto

## ID
A1

## Trilha
A — Presença

## Status
🎯 pronto pra delegar — todas as decisões fechadas em 2026-05-14

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
- Config via `.env`: `AQUARIUM_WS_URL` (default
  `ws://localhost:8080/ws`) e `AQUARIUM_ENABLED` (default `false`,
  pra não obrigar o aquário estar de pé em todo dev local nem nos
  E2E). Não há auth — é tudo loopback.
- Heartbeat: WS native `ping`/`pong`. A biblioteca `websockets`
  cuida via `ping_interval`/`ping_timeout` — não precisa
  protocolo app-level.
- Reconnect com backoff exponencial 1s → 2s → 5s → 10s → 30s,
  jitter de ±20%, cap em 30s. Sem limite de tentativas.
- Testes unitários sobre o mapeamento de fase → mensagem (sem
  conexão real).

### Fora
- Campo `project` no payload — fica mockado pro slug do
  `TARGET_PROJECT_PATH` por enquanto. A3 troca por valor real.
- Identidade visual dos Meeseeks (`name` "Meeseeks-XXXX") — Camada C
  é A2.
- O serviço aquário em si. Não conhecemos detalhes do servidor
  além do protocolo recebido.
- `event recovered` — não há fonte natural no MMB hoje. Meeseeks
  só decresce até morrer. Fica fora desta versão (acordo fechado
  com o time do aquário; vide "Decisões fechadas").

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
9. **Conexão real validada localmente**: com o servidor do
   aquário rodando em `ws://localhost:8080/ws` e o front aberto
   no browser, um `/meeseeks` smoke faz o Meeseeks aparecer,
   decair, e morrer na tela. Vide seção "Como ver na prática"
   abaixo.

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

### Spec do aquário (fechada com o time deles)

WebSocket one-way (push do MMB). Endpoint local `ws://localhost:8080/ws`,
sem TLS, sem auth, sem tenant — instância única do MMB ↔ instância
única do aquário, lado a lado em dev.

3 tipos de mensagem JSON, discriminadas por `type`:

```jsonc
// snapshot — estado completo no connect (também reusável como reset)
{
  "type": "snapshot",
  "meeseeks": [
    {
      "id": "task-42",         // string, obrigatório
      "health": 0.83,          // number 0..1, opcional (default 1)
      "isFreakingOut": false,  // boolean, opcional (default false)
      "name": "Meeseeks-7e3a", // string, opcional, ≤32 chars
      "task": "rebalance ..."  // string, opcional
    }
  ]
}

// state — update absoluto de saúde
{"type": "state", "id": "task-42", "health": 0.74}

// event — transições discretas
{"type": "event", "kind": "born",
 "id": "task-42", "name": "Meeseeks-7e3a", "task": "..."}
{"type": "event", "kind": "died_happy",    "id": "task-42"}
{"type": "event", "kind": "died_defeated", "id": "task-42"}
{"type": "event", "kind": "freaking_out",  "id": "task-42"}
// "recovered" não emitido — Meeseeks não recupera no MMB
```

Regras operacionais (do lado deles, importantes pro nosso código):

- Ordem **FIFO** por conexão. Não precisa serializar do lado do MMB.
- `snapshot` é tratado como **reset** completo no lado deles. Útil
  como "anúncio de estado" no reconnect.
- `state` ou `event != born` referente a `id` desconhecido é
  **dropado silenciosamente** — `born` é o único jeito de um
  Meeseeks aparecer. Garantir essa ordem é obrigação do cliente.
- `state` pra `id` que já morreu também é dropado.
- `freaking_out` e `born` são idempotentes; podem ser reenviados
  sem efeito.
- Payload inválido (campo faltando, tipo errado) é dropado, conexão
  segue viva — não fechamos por causa de uma mensagem ruim.
- `name` ≤32 chars (truncar antes de mandar). `task` aceita texto
  livre, até KB.

Mapeamento de decay → health (esboço, calibrar na implementação):

| Tempo do Meeseeks | Frase decay | Health proposta |
|---|---|---|
| 0-3min | Working on it! | 1.0 → 0.85 |
| 3-8min | Caaaaan do! | 0.85 → 0.65 |
| 8-15min | Oh boy, this is tricky | 0.65 → 0.40 |
| 15-25min | Existing is becoming pain | 0.40 → 0.15 (`freaking_out`!) |
| 25min+ | Pleeease let me finish | 0.15 → 0.05 |

## Implementação sugerida

### Princípio arquitetural

Espelhe o que foi feito com `logger/` no Ato VI: o módulo
`aquario/` é **completamente desacoplado** do core. Zero `import
discord` dentro dele. Bot.py só "puxa" o módulo como adapter
externo e chama `emit(...)` nos pontos canônicos. Falha do
aquário não derruba o bot. Mesmo padrão de "side car observável"
do logger.

### Estrutura

```
aquario/
├── __init__.py
├── client.py        # WebSocket client com reconnect + ring buffer
├── messages.py      # dataclasses + serializer (Snapshot, State, Event)
└── lifecycle.py     # converte phase/elapsed → mensagem (funções puras)
```

`client.py`: classe `AquarioClient` com `start()`, `stop()`,
`emit(message)`. `emit` enfileira; uma task asyncio drena a fila
no socket. Reconnect transparente. Ping/pong delegado à lib
`websockets` (`ping_interval=20`, `ping_timeout=10` ou
similares).

`lifecycle.py`: funções puras testáveis sem mock de IO.
`health_from_elapsed(s)`, `event_for_phase(phase) -> Optional[Event]`,
etc. Mesmo padrão do `_parse_shortstat` e do `_is_transient_autoupdate`.

Hook em `bot.py`: instancia o cliente em `on_ready` (igual ao
`_logger`). Cada `_send_*` chama `_aquario.emit(...)` (best-effort,
nunca raises).

Para `state` periódico: aproveite a task `_heartbeat` async que já
roda durante o run. Em vez de só editar o Discord, também emite
state pro aquário a cada tick.

### Invariante crítico

`event born` precisa ser emitido **antes** de qualquer `state` ou
outro `event` pro mesmo `id`. O aquário dropa silenciosamente
mensagens pra `id` desconhecido. Implemente isso explicitamente
em `bot.py` (emite born imediatamente no spawn do Meeseeks, antes
de qualquer outra coisa).

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

## Decisões fechadas

Estas decisões foram alinhadas com o Rick e com o time do aquário.
Não precisa reconfirmar antes de implementar.

1. **`event recovered` fica fora.** MMB não emite. Meeseeks decai
   monotônico até morrer.
2. **Ring buffer = 1000 mensagens.** Suficiente pra absorver
   disconnect de minutos a rate <1msg/s. Descarta a mais antiga
   quando cheio.
3. **`AQUARIUM_ENABLED=false` é o default** no `.env`. Bot opera
   normalmente sem o aquário; só conecta quando o flag é `true`.
4. **Endpoint**: `ws://localhost:8080/ws` (default em `config.py`).
   Sem TLS, sem auth. Override via `AQUARIUM_WS_URL` se necessário.
5. **Library**: `websockets` (não-versionada, pegar a mais nova
   estável). Async-nativa, suporta `ping_interval`/`ping_timeout`
   embutido. Adicionar ao `requirements.txt`. Confirmar antes que
   não tem outra lib WS no projeto.
6. **Reconnect**: 1s → 2s → 5s → 10s → 30s, ±20% jitter, cap 30s,
   sem limite de tentativas.
7. **Tenant / `project` field**: fora desta versão. Será aditivado
   quando B1 (multi-projeto) for entregue — backward-compatible
   pelo lado deles.

## Como ver na prática

Pra validar o critério #9 ponta a ponta, três processos em
paralelo no localhost (cada um em um terminal):

```bash
# Terminal 1 — servidor do aquário (deles)
cd <repo-do-aquario>
<comando deles pra subir o WS server na porta 8080>

# Terminal 2 — front do aquário (deles)
cd <repo-do-aquario-front>
<comando deles pra abrir o front no browser>

# Terminal 3 — MMB com aquário ligado
cd <raíz-do-MMB>
AQUARIUM_ENABLED=true .venv/bin/python bot.py
```

Com isso de pé, dispara um `/meeseeks` qualquer no Discord. Você
deve ver no browser:

- Meeseeks aparecer (`born`) imediatamente.
- Saúde decair gradual ao longo do run.
- Se passar dos 15min, sprite entra em pânico (`freaking_out`).
- No fim, some com brilho (`died_happy`) ou fade triste
  (`died_defeated`).

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
