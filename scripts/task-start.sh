#!/usr/bin/env bash
# Cria worktree + branch isolada pra trabalhar numa task do MMB.
#
# Uso:
#   scripts/task-start.sh <task-id>
#
# Exemplo:
#   scripts/task-start.sh C1
#
# Resultado: worktree em .worktrees/<id>-<slug> com branch
# task/<id>-<slug> baseada num master atualizado.

set -euo pipefail

TASK_ID="${1:-}"
if [ -z "$TASK_ID" ]; then
  echo "Uso: $0 <task-id>"
  echo
  echo "Tasks 🎯 prontas pra delegar (ver docs/tasks/INDEX.md):"
  for f in docs/tasks/[A-Z][0-9]*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .md)
    id="${name%%-*}"
    echo "  - $id  ($f)"
  done
  exit 1
fi

# Garante raiz do MMB
if [ ! -f "CLAUDE.md" ] || [ ! -d "docs/tasks" ]; then
  echo "ERRO: rode da raiz do MMB (onde estão CLAUDE.md e docs/tasks/)."
  exit 1
fi

# Localiza o brief da task (case-insensitive na id)
TASK_FILE=$(ls docs/tasks/${TASK_ID}-*.md 2>/dev/null | head -1 || true)
if [ -z "$TASK_FILE" ]; then
  echo "ERRO: task '$TASK_ID' não encontrada em docs/tasks/."
  echo "Tasks disponíveis:"
  ls docs/tasks/[A-Z][0-9]*.md 2>/dev/null | xargs -n1 basename | sed 's/^/  /'
  exit 1
fi
SLUG=$(basename "$TASK_FILE" .md)  # ex: C1-retry-transiente

WORKTREE_PATH=".worktrees/${SLUG}"
BRANCH="task/${SLUG}"

# Atualiza master se possível (sem falhar se offline)
echo "→ atualizando master local..."
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "master" ]; then
  git pull --ff-only 2>/dev/null || echo "  (pull falhou — seguindo com master local)"
else
  git fetch origin master --quiet 2>/dev/null || echo "  (fetch falhou — seguindo com master local)"
fi

# Se worktree já existe, é re-entrada — só relembra o caminho
if [ -d "$WORKTREE_PATH" ]; then
  echo
  echo "Worktree já existe: $WORKTREE_PATH"
  echo "Branch: $BRANCH"
  echo
  echo "Pra continuar:"
  echo "  cd $WORKTREE_PATH"
  echo "  claude"
  exit 0
fi

# Cria worktree + branch
echo "→ criando worktree $WORKTREE_PATH (branch $BRANCH)..."
git worktree add -b "$BRANCH" "$WORKTREE_PATH" master

echo
echo "✓ Worktree pronta: $WORKTREE_PATH"
echo "✓ Branch: $BRANCH (a partir de master)"
echo
echo "Próximos passos:"
echo "  cd $WORKTREE_PATH"
echo "  cat docs/tasks/${SLUG}.md     # leia o brief antes de tudo"
echo "  claude                          # inicia agente nessa worktree"
echo
echo "Ao terminar (após PR mergeado):"
echo "  scripts/task-end.sh $TASK_ID"
