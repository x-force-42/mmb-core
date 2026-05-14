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
| **C1** | Retry transiente no claude_runner | C — Robustez | 🎯 pronto | [`C1-retry-transiente.md`](C1-retry-transiente.md) |
| **C2** | Cenários E2E de erro | C — Robustez | 🎯 pronto | [`C2-cenarios-e2e-erro.md`](C2-cenarios-e2e-erro.md) |
| A2 | Identidade visual (Camada C+E) | A — Presença | ⬜ não iniciado | (sem brief) |
| A3 | Aquário multi-projeto | A — Presença | 🔒 bloqueado por B1 | (sem brief) |
| B2 | Garagem com contexto persistente | B — Plataforma | ⬜ decisão em aberto | (sem brief) |
| B3 | Modelo por fase (Opus Garagem, Sonnet Meeseeks) | B — Plataforma | ⬜ não iniciado | (sem brief) |
| C3 | Cenário E2E anti-escopo | C — Robustez | ⬜ não iniciado | (sem brief) |
| C4 | Calibração com cenários reais | C — Robustez | 🔒 bloqueado por C2 | (sem brief) |

## Matriz de paralelismo

Quais tasks podem rodar simultaneamente sem conflito de merge?

| | A1 | B1 | C1 | C2 |
|---|---|---|---|---|
| **A1** | — | ⚠️ conflito em `bot.py` | ✅ ok | ✅ ok |
| **B1** | ⚠️ conflito em `bot.py` | — | ✅ ok | ✅ ok |
| **C1** | ✅ ok | ✅ ok | — | ✅ ok |
| **C2** | ✅ ok | ✅ ok | ✅ ok | — |

**Lance C1 e C2 hoje em paralelo.** A1 sequencial depois. B1 só
depois que A1 mergear.

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
