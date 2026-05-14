# Progresso — MMB

Log enxuto de marcos. Atualizar a cada milestone, **não** a cada commit.
Mais recente no topo.

---

## 2026-05-14 — API do cockpit operacional (E1)

### E1 entregue (commit `f2aa145`)

Primeira task da trilha E entregue por agente externo, totalizando
**5 tasks por delegação** em sequência (C1, C2, E0, E1 + scaffold).

- Novo módulo `api/` com FastAPI thin layer sobre o logger SDK:
  - `api/app.py` — FastAPI + CORS + startup.
  - `api/models.py` — Pydantic v2 schemas.
  - `api/routes/{runs,projects,metrics}.py` — 5 endpoints REST.
  - `api/deps.py` — singleton do RunLogger.
  - `api/README.md` — doc inline.
- `RunLogger` ganhou 4 métodos novos:
  - `list_runs(...)` com filtros (project, phase, datas, paginação,
    ordering).
  - `list_projects()` lista cadastro.
  - `update_run_review(...)` PATCH-only nos 3 campos manuais
    (`merged_to_main`, `assertiveness_score`, `review_note`).
  - `overview_metrics(days=30)` agregados pro dashboard.
- Processo separado: `scripts/api.sh` sobe `uvicorn api.app:app`
  em `MMB_API_PORT` (default 8765). Independência total — bot
  funciona sem API e vice-versa.
- `requirements.txt` formalizado (antes era implícito no .venv):
  discord.py, python-dotenv, fastapi, uvicorn[standard], pydantic.
- CORS habilitado pra `http://localhost:5173` (Vite default do
  futuro repo `mmb-cockpit`).
- **+39 testes novos** em 4 arquivos (`test_api_cors`,
  `test_api_metrics`, `test_api_projects`, `test_api_runs`) e
  expansão de `test_logger.py`. Total da suíte: **236 verdes**.

### Marcos cumulativos do sistema de delegação

| Task | Entregue em | Comportamento do agente |
|---|---|---|
| C1 | `b530cca` | Refactor cirúrgico, sem scope creep |
| C2 | `ff08269` | Pivô consciente em 3 estratégias, escopo intocado |
| E0 | (discovery) | Não foi delegado — discussão direta no chat |
| E1 | `f2aa145` | Estrutura aderente ao brief, +39 testes |

### Implicação prática

A trilha E destrava a próxima frente: criação do repo separado
`mmb-cockpit` (Vite/React/Vitest) consumindo a API local. **E2+
agora é o próximo passo natural pra ter o cockpit no ar.**

### Estado pós-E1

- Worktrees ativas: A1 (em curso), mais C1/C2/E1 (pendentes
  cleanup via `task-end.sh`).
- Master: `f2aa145`. 236 testes verdes em ~30s.
- B1 agora pode rodar em paralelo com A1 se aceitar conflito em
  `bot.py` — mas recomendação fica sequencial (A1 mergeie primeiro).

---

## 2026-05-14 — trilha C inteira fechada (C1 + C2)

### C2 entregue (commit `ff08269`)

Segunda task externa via PROTOCOLO. Adicionou 3 cenários E2E:

- `03_vague_prompt_pushback` — task.txt vaga ("Melhore o código.")
  força `garagem_pushback`, verify confere `duvidas_pro_rick ≥ 1`.
- `04_meeseeks_failure_impossible` — setup quebra `npm run build`
  do fixture via mutação em `package.json` (commit no master,
  cleanup auto reverte); verify confere `meeseeks_outcome=failure`
  e `commits == []`.
- `05_garagem_no_slug` — descartado conforme brief (fase não
  triggerável organicamente, opções deixadas em decisões abertas
  do brief pra futuro).

### Lição calibrada (vai pro C4)

O agente tentou três estratégias antes de achar uma que produzisse
`meeseeks_failure` consistente:

1. Biblioteca inexistente → Garagem pushbackou (leu `AGENTS.md`).
2. Teste pré-quebrado → Meeseeks racionalizou "não fui eu que
   quebrei".
3. Build quebrado → funcionou (binário, sem brecha pra
   racionalização).

Indica que `skills/meeseeks.md` passo 3 lê "minhas mudanças
quebraram?" e não "tudo verde, ponto" — decisão consciente quando
desenharmos C4. Custo da calibração ~$0.40, ~7min.

### Estado do sistema de delegação

C1 e C2 mergeadas via mesmo ritual: `task-start.sh` → agente
externo → PR → `task-end.sh`. Zero intervenção pontual minha. Suite
E2E sai de 2 cenários (só success) pra 4 (cobre 3 fases distintas
do PipelineResult). 197 testes unit/integration verdes.

### Estado pós-Trilha C

- Branches sobrando: `task/C1-retry-transiente` e
  `task/C2-cenarios-e2e-erro`. Worktrees idem. Cleanup via
  `scripts/task-end.sh C1 C2`.
- Próximo lote 🎯: A1 (Presença, sequencial, toca `bot.py`)
  e B1 (Plataforma, espera A1 mergeie).

---

## 2026-05-14 — primeira task entregue por agente externo

### C1 fechado (commit `b530cca`)

Validação ponta-a-ponta do sistema de delegação multi-agente:

- Rick lançou `scripts/task-start.sh C1` → worktree e branch criadas.
- Agente Claude em sessão separada consumiu `docs/tasks/C1-retry-transiente.md`
  como autoridade do escopo, sem briefing adicional.
- Entrega respeitou o brief integralmente: só `claude_runner.py` +
  seu teste, decisão em aberto (delays) ficou no default sugerido,
  zero pulo de hook, zero scope creep.
- Bônus de qualidade: agente extraiu `_is_transient_autoupdate` como
  helper testável separado de `_run_claude_p_once`, casando com o
  padrão "parsing puro fora do IO" que aplicamos no `_parse_shortstat`
  durante o Ato VII.
- 197 testes verdes (192 anteriores + 5 novos cobrindo: recovery
  via FileNotFoundError, recovery via exit 2, exaustão de retries,
  não-retry em exit 1 genérico, não-retry em timeout).

### Implicação prática

O race do auto-update do CLI (documentado em `CLAUDE.md` e
manifesto duas vezes durante o desenvolvimento do E2E) deixa de
afetar produção e suite E2E. 2 retries com backoff 1.5s+3s cobrem
a janela transiente típica.

### Estado do sistema de delegação

Funciona como previsto. `docs/tasks/PROTOCOLO.md` foi seguido sem
intervenção. C2 está em curso por outro agente em paralelo.

---

## 2026-05-13 — virada de eixo · `v0.5.0` candidato

### Atos VI + VII consolidados

**Ato VI — Observabilidade** (commits `046abdb` + `086c002`)

- `logger/` SDK desacoplado em SQLite. Tabelas `projects` + `runs`,
  schema rico (tokens, custo, diff stats, outcome por fase, review
  manual). 29 testes próprios em `:memory:`.
- Integração ao `bot.py`: `start_run` → `record_garagem` →
  `record_meeseeks` → `record_dev_server` → `finish_run`, com
  helpers `_garagem_entry`/`_meeseeks_entry` mantendo o handler
  enxuto. `_send_*` permanecem só renderizando embed.
- Captura de `tokens_input/output`, `cost_usd` (via
  `total_cost_usd` do envelope — bug histórico corrigido) e `diff
  stats` via `git diff --shortstat`.
- Garagem ganhou `criticidade` e `complexidade` no schema do briefing.
- Visualização via Datasette: `datasette mmb.db -m datasette_metadata.json`,
  facets default + 4 queries salvas (últimos runs, custo/dia, taxa
  de pushback, falhas pra investigar).
- +17 testes cobrindo o contrato com o envelope real do CLI,
  propagação de tokens/cost em cada camada, e `_parse_shortstat`
  em 9 formatos do git.

**Ato VII — Arnês E2E** (commit `d279e6c`)

- Fixture isolado em repo separado (`~/llab/mmb-fixture`, commit
  `17ca392`): zero deps, `node --test` nativo, `tests/pending/`
  ativável por cenário, `dev-server` stub na :5173.
- `tests/e2e/harness.py` + `conftest.py` com cleanup automático:
  reset pro SHA pristine, remove worktrees + branches `meeseeks/*`,
  mata processo na :5173.
- 2 cenários verdes em 2min20s, ~US$0.10 por suite:
  - `01_rename_greet_to_welcome` — validação por grep + DB row
  - `02_implement_farewell` — contrato via teste pré-escrito, `npm
    test` no worktree real
- `scripts/e2e.sh` como entrypoint dedicado, fora do `pytest`
  default. Marker `e2e` registrado, testpaths narrow.
- `docs/cenarios-e2e.md` — guia de autoria (princípios,
  anti-padrões, catálogo desejado).

### Virada de eixo estratégico

A visão deixou de ser "bot de uma feature" e passou a ser
**plataforma multi-projeto de execução determinística por agentes**.
Detalhes em `docs/arvore.md`. Implicações:

- Conceito de **projeto como cidadão de 1ª classe** (matar
  `TARGET_PROJECT_PATH`, registrar projetos via slash command).
- **Garagem com contexto persistente** por projeto, em Opus.
- **Aquário de Meeseeks** como visualização ao vivo (WebSocket
  push, snapshot + state + event). Spec recebida do time do
  aquário, mapeamento ao MMB feito.
- Trabalho passa a ser **três trilhas paralelas** (Presença,
  Plataforma, Robustez) em vez de atos sequenciais.

### Sistema de delegação para agentes paralelos

`docs/tasks/` + `scripts/task-start.sh` permitem lançar várias
sessões do Claude CLI em paralelo, cada uma em worktree própria,
trabalhando em tasks diferentes sem conflito de merge. CLAUDE.md
ganhou seção de bootstrap que faz o agente identificar tasks
abertas e perguntar qual atacar.

### Status

- 192 testes unit/integration verdes em ~3s, +2 E2E em ~2min.
- 4 tasks 🎯 prontas pra delegar (A1, B1, C1, C2).
- Master limpa, pronta pra tag `v0.5.0` quando você decidir.

---

## 2026-05-13 — `v0.3.0` guardrails de teste consolidados

### Imersão temática (consolidada após smoke)

- Camadas **A (microcopy)** e **B (heartbeat com decay)** validadas em
  produção via Discord. Detalhes em `docs/plano-imersao.md`.

### Refactor modular (`v0.2.0`)

Pipeline ponta-a-ponta inalterado, mas separado em peças focadas:

- `formatters.py` + `parsing.py` (funções puras, sem deps)
- `claude_runner.py` (subprocess do `claude -p` unificado: env,
  timeout, exit code, envelope JSON, FileNotFoundError)
- `pipeline.py` — `run_pipeline()` headless devolve `PipelineResult`
  com fase terminal entre as 6 possíveis
- `bot.py` linear: `_run_with_heartbeat` + 6 funções `_send_*` por
  fase, command handler de ~40 linhas

### Guardrails de teste (`v0.3.0`)

- pytest + pytest-asyncio + pytest-cov no `.venv`
- **116 testes verdes em ~1.5s, 89% cobertura total**
- Como rodar: `.venv/bin/pytest [--cov]`

Distribuição:

| Suite | Testes | Cobertura |
|---|---|---|
| `test_formatters.py` | 44 | 100% formatters.py |
| `test_parsing.py` | 18 | 100% parsing.py |
| `test_pipeline.py` | 12 | 100% pipeline.py |
| `test_garagem.py` | 4 | 100% garagem.py |
| `test_meeseeks.py` | 15 | 71% meeseeks.py |
| `test_claude_runner.py` | 13 | 95% claude_runner.py |
| `test_worktree.py` (integração) | 10 | git real em repo dummy |

### Dívida explícita de teste

- **Dev server** (`start_dev_server`, `stop_dev_server`, `_kill_port`):
  cobertura requer integração com OS ou mocks pesados — adiada.
- **`config.py`** validação em import-time: cobertura pediria Fase 3
  do refactor (Config dataclass injetada) — adiada.
- **`claude_runner.py:102-103`** (`ProcessLookupError` em `proc.kill`):
  edge case raro, não vale.

### Próxima frente — opções abertas

- **Camada D** de imersão (embeds Discord + cores + avatar)
- **Cenários de calibração** (catálogo manual dos 5 cenários reais
  do PO/DEV — primeira fase do plano científico de calibração)

---

## 2026-05-12

### Estrutura base

- Bot Discord (`bot.py`), carregamento de env (`config.py`).
- Garagem como sub-Claude read-only (`garagem.py` + `skills/garagem.md`):
  schema JSON estrito com `slug`, `commit_tipo`, `commit_descricao`
  em inglês.
- Meeseeks como sub-Claude full perms (`meeseeks.py` + `skills/meeseeks.md`):
  pipeline obrigatório (`npm test` → implementar → escrever testes →
  `npm test` → `npm run build` → commit).
- Auto-chain Garagem → Meeseeks no bot.

### Sandbox de execução

- Git worktree isolada em `<projeto>/.worktrees/<slug>/`.
- Branch dedicada `meeseeks/<slug>`, baseada em `master`.
- Symlink de `node_modules` da raiz pra worktree (sem reinstalar).
- `.worktrees/` no `.gitignore` do projeto-alvo.

### Dev server

- Bot mantém o `npm run dev` (subprocess detached) na porta 5173.
- Mata o anterior dele + qualquer processo na porta antes de subir.
- Comandos de cleanup retornam no relatório final pro Rick rodar.

### Robustez

- `FileNotFoundError` no spawn do `claude` agora retorna erro
  estruturado em vez de derrubar interaction (vide auto-update do
  Claude Code reescrevendo symlink).
- `DISABLE_AUTOUPDATER=1` no env dos subprocessos pra fechar a janela
  de corrida na origem.

### Calibração da Garagem

- Orçamento de exploração: ≤5 Reads, senão pushback.
- Refactor adjacente com três casos (mecânico no briefing, oportunista
  fora, pré-requisito não-trivial em pushback).
- `criterio_de_pronto` rigoroso: teste nomeado ou roteiro manual.

### Versionamento

- `git init` na raiz do MMB.
- Commit inicial `5ab35c3` em `master`.
- `.env`, `.venv/`, `__pycache__/`, `.claude/settings.local.json`
  fora do versionamento.
