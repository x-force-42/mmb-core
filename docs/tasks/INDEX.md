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
| **E0** | Discovery — Cockpit de Operações | E — Cockpit | 🟡 em curso (conversação) | [`E0-discovery-cockpit.md`](E0-discovery-cockpit.md) |
| A2 | Identidade visual (Camada C+E) | A — Presença | ⬜ não iniciado | (sem brief) |
| A3 | Aquário multi-projeto | A — Presença | 🔒 bloqueado por B1 | (sem brief) |
| B2 | Garagem com contexto persistente | B — Plataforma | ⬜ decisão em aberto | (sem brief) |
| B3 | Modelo por fase (Opus Garagem, Sonnet Meeseeks) | B — Plataforma | ⬜ não iniciado | (sem brief) |
| C3 | Cenário E2E anti-escopo | C — Robustez | ⬜ não iniciado | (sem brief) |
| C4 | Calibração com cenários reais | C — Robustez | ⬜ desbloqueado | (sem brief) |
| E1+ | Implementação do cockpit | E — Cockpit | 🔒 espera E0 fechar | (a definir) |
| ~~C1~~ | Retry transiente no claude_runner | C — Robustez | ✅ fechado em `b530cca` | [`C1-retry-transiente.md`](C1-retry-transiente.md) |
| ~~C2~~ | Cenários E2E de erro | C — Robustez | ✅ fechado em `ff08269` | [`C2-cenarios-e2e-erro.md`](C2-cenarios-e2e-erro.md) |

## Matriz de paralelismo

Quais tasks 🎯 podem rodar simultaneamente sem conflito de merge?

| | A1 | B1 |
|---|---|---|
| **A1** | — | ⚠️ conflito em `bot.py` |
| **B1** | ⚠️ conflito em `bot.py` | — |

Com trilha C limpa (C1 + C2 mergeadas), o próximo movimento é
**A1 sequencial**, depois **B1**. Em paralelo a A1, dá pra abrir
C3 (anti-escopo, só cria arquivos em `tests/e2e/scenarios/`) ou
C4 (calibração, só lê do logger) sem conflito.

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
