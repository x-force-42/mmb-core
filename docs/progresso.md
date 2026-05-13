# Progresso — MMB

Log enxuto de marcos. Atualizar a cada milestone, **não** a cada commit.
Mais recente no topo.

---

## 2026-05-13

### Em teste — aguardando validação manual via Discord

- **Camada A (microcopy)** — voz Mr. Meeseeks nos pontos de transição.
  Detalhes em `docs/plano-imersao.md`.
- **Camada B (heartbeat com decay)** — heartbeat do Meeseeks varia
  conforme tempo de execução. Tabela em `docs/plano-imersao.md`.

Ambos implementados em `bot.py`. Bot precisa ser reiniciado pra
carregar. Validar com uma `/meeseeks` simples e observar se o spawn,
sucesso, falha e o heartbeat de tarefas longas refletem as mudanças.

### Próxima frente

- **Camada de testes do workflow**: documentar protocolo de teste
  ponta-a-ponta do pipeline Garagem → Meeseeks → dev server → cleanup.
  Discussão em andamento — definir o "sisteminha mínimo pra testar"
  antes de partir pra camada D.

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
