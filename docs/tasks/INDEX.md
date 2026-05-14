# Tasks abertas — MMB

Índice canônico de tasks em aberto. Toda task que se quer trabalhar
**precisa** estar aqui antes — é o registro autoritativo, espelhado
em `docs/arvore.md` mas indexado pra consumo de agente.

## Como agente: use isto

Você está em uma sessão recém-iniciada e o Rick ainda não disse
o que quer fazer? Siga:

1. Cheque o pré-flight em `docs/tasks/PROTOCOLO.md`.
2. Apresente a lista de tasks 🎯 abaixo via `AskUserQuestion`.
3. Quando o Rick escolher, leia o brief correspondente em
   `docs/tasks/<id>-<slug>.md`.
4. Confirme alinhamento sobre decisões em aberto do brief, se houver.
5. Trabalhe.

## Status atual

| ID | Título | Trilha | Status | Brief |
|---|---|---|---|---|
| **A1** | Aquário mono-projeto | A — Presença | 🎯 pronto | [`A1-aquario-mono.md`](A1-aquario-mono.md) |
| **B1** | Projetos como cidadão 1ª classe | B — Plataforma | 🎯 pronto | [`B1-projetos-1a-classe.md`](B1-projetos-1a-classe.md) |
| **E1** | API do Cockpit de Operações | E — Cockpit | 🎯 pronto | [`E1-api-cockpit.md`](E1-api-cockpit.md) |
| A2 | Identidade visual (Camada C+E) | A — Presença | ⬜ não iniciado | (sem brief) |
| A3 | Aquário multi-projeto | A — Presença | 🔒 bloqueado por B1 | (sem brief) |
| B2 | Garagem com contexto persistente | B — Plataforma | ⬜ decisão em aberto | (sem brief) |
| B3 | Modelo por fase (Opus Garagem, Sonnet Meeseeks) | B — Plataforma | ⬜ não iniciado | (sem brief) |
| C3 | Cenário E2E anti-escopo | C — Robustez | ⬜ não iniciado | (sem brief) |
| C4 | Calibração com cenários reais | C — Robustez | ⬜ desbloqueado | (sem brief) |
| E2+ | Frontend do Cockpit (repo separado) | E — Cockpit | 🔒 espera E1 + repo `mmb-cockpit` | (fora deste repo) |
| ~~C1~~ | Retry transiente no claude_runner | C — Robustez | ✅ fechado em `b530cca` | [`C1-retry-transiente.md`](C1-retry-transiente.md) |
| ~~C2~~ | Cenários E2E de erro | C — Robustez | ✅ fechado em `ff08269` | [`C2-cenarios-e2e-erro.md`](C2-cenarios-e2e-erro.md) |
| ~~E0~~ | Discovery — Cockpit de Operações | E — Cockpit | ✅ fechado em 2026-05-14 | [`E0-discovery-cockpit.md`](E0-discovery-cockpit.md) |

## Matriz de paralelismo

Quais tasks 🎯 podem rodar simultaneamente sem conflito de merge?

| | A1 | B1 | E1 |
|---|---|---|---|
| **A1** | — | ⚠️ conflito em `bot.py` | ✅ ok |
| **B1** | ⚠️ conflito em `bot.py` | — | ⚠️ conflito em `logger/` |
| **E1** | ✅ ok | ⚠️ conflito em `logger/` | — |

Dá pra rodar **A1 e E1 em paralelo agora mesmo** — A1 toca
`aquario/` + `bot.py`, E1 toca `api/` + `logger/`. Conjuntos
disjuntos. **B1** entra depois que A1 mergear (mesmo `bot.py`)
ou depois que E1 mergear (mesmo `logger/`).

C3 (só cria em `tests/e2e/scenarios/`) e C4 (depende de C2, só lê
logger) continuam compatíveis com qualquer combinação.

## Como criar uma task nova

1. Adicione a entrada na tabela acima.
2. Crie o brief em `docs/tasks/<id>-<slug>.md` seguindo o esqueleto
   abaixo. Idealmente espelhe a estrutura dos briefs prontos.
3. Atualize `docs/arvore.md` com o ato correspondente.
4. Atualize esta matriz de paralelismo se a task tocar arquivos
   compartilhados.

### Esqueleto de brief

```
# Task <ID> — <título curto>

## ID
## Trilha
## Status
## Intenção
## Escopo (dentro / fora)
## Critério de pronto
## Contexto técnico (arquivos relevantes, ponteiros)
## Implementação sugerida (hints; agente decide)
## Testes a adicionar
## Decisões em aberto
## Dependências (bloqueia / bloqueado por)
## Conflito potencial com (outras tasks que tocam arquivos comuns)
## Estimativa
```
