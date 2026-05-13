# Progresso — MMB

Log enxuto de marcos. Atualizar a cada milestone, **não** a cada commit.
Mais recente no topo.

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
