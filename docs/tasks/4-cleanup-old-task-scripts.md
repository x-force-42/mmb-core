# chore(scripts): remove `task-start.sh` e `task-end.sh` legados

> Brief espelhado da sub-issue [#4](https://github.com/x-force-42/mmb-core/issues/4).
> Single-repo, single-task — **não tem épico**. Issue solta em
> `mmb-core` com labels `task,project:mmb-core`.

## Identidade

- **Slug:** `cleanup-old-task-scripts`
- **Projeto:** `mmb-core`
- **Tipo:** chore / cleanup

## Intenção

Remover os scripts legados `scripts/task-start.sh` e
`scripts/task-end.sh` do `mmb-core`. Foram substituídos pelos
generalizados em `.tooling/bin/task-start.sh` e
`.tooling/bin/task-end.sh` (que vivem no andaime cross-repo
`/MMB/.tooling/` e aceitam `<repo>` como 1º argumento, detectam
default branch automaticamente e tratam squash-merge).

Atualizar também as docs vivas que ainda apontam pro comando
antigo.

## Escopo

### Dentro

- Deletar `scripts/task-start.sh`
- Deletar `scripts/task-end.sh`
- Atualizar `CLAUDE.md` (linhas ~103, ~117) — substituir
  `scripts/task-start.sh <id>` por
  `.tooling/bin/task-start.sh mmb-core <id>` (idem task-end).
- Atualizar `docs/ORQUESTRADOR.md` (~linha 104) — mesma
  substituição.
- Atualizar `docs/tasks/PROTOCOLO.md` (~linhas 33, 133) — mesma
  substituição.
- Grep final: `git grep "scripts/task-"` deve sobrar **apenas** em
  `docs/progresso.md` (registro histórico, preservar).

### Fora

- **NÃO mexer** em `docs/progresso.md`. É diário narrativo do
  projeto; menções aos scripts antigos são fato histórico e
  reescrever apagaria registro de como o método evoluiu.
- **NÃO mexer** em `scripts/api.sh` nem `scripts/e2e.sh`. São
  scripts de produto (sobem API e rodam suíte E2E),
  não infra de andaime.
- **NÃO criar wrappers** em `scripts/` que chamem o novo
  comando. Quem usa o andaime sabe rodar do path novo.

## Critério de pronto

- [ ] `scripts/task-start.sh` e `scripts/task-end.sh` deletados.
- [ ] `CLAUDE.md`, `docs/ORQUESTRADOR.md`, `docs/tasks/PROTOCOLO.md`
      apontam pra `.tooling/bin/task-{start,end}.sh mmb-core <id>`.
- [ ] `git grep "scripts/task-"` retorna apenas matches em
      `docs/progresso.md`.
- [ ] Commit em Conventional Commits
      (`chore(scripts): remove legacy task-*.sh`).

## Contexto técnico

Arquivos relevantes:

- `scripts/task-start.sh` — a remover
- `scripts/task-end.sh` — a remover
- `scripts/api.sh` — preservar (produto)
- `scripts/e2e.sh` — preservar (produto)
- `CLAUDE.md`, `docs/ORQUESTRADOR.md`, `docs/tasks/PROTOCOLO.md` —
  docs vivas a atualizar
- `docs/progresso.md` — registro histórico, preservar como está

Pre-check feito pelo mestre:

- Nenhuma chamada a `scripts/task-*` em `Makefile`, `.github/`
  ou `README.md`.

## Implementação sugerida

Mecânico:

1. `git rm scripts/task-start.sh scripts/task-end.sh`
2. Sed/edit pontual nas 3 docs vivas substituindo
   `scripts/task-start.sh <id>` por
   `.tooling/bin/task-start.sh mmb-core <id>` (idem task-end).
   Atenção: redação ao redor pode mencionar "rode da raiz do MMB"
   ou similar — o comando novo roda do andaime, não do repo;
   ajustar texto vizinho se ficar inconsistente.
3. Confirmar com `git grep "scripts/task-"`.
4. Commit + PR.

## Decisões em aberto

Nenhuma.

## Estimativa

~30 minutos.

## Definition of Done formal

- [ ] Critério de pronto todo check.
- [ ] PR linka `Closes #4` no body.
- [ ] Issue fecha automaticamente.
- [ ] Worktree limpa via `.tooling/bin/task-end.sh mmb-core 4`.
