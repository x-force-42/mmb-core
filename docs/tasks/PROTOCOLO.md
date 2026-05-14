# Protocolo de operação para agentes

Este documento descreve como uma sessão do Claude CLI (ou outro
agente) deve operar quando inicia em uma worktree do MMB para
executar uma task. Vale para todas as tasks em `docs/tasks/`.

Se você é um agente lendo isto pela primeira vez nesta sessão:
**leia até o fim antes de tocar em qualquer arquivo.**

## Princípio único

Sessões paralelas trabalhando em tasks diferentes nunca podem
conflitar. Isso só é verdade se cada uma operar em sua própria
**worktree git** com sua própria **branch**, derivada de um
`master` atualizado.

Tudo aqui decorre desse princípio.

## Pré-flight obrigatório (antes de QUALQUER edit)

Antes de modificar um único arquivo, valide os 4 invariantes:

### 1. Você está numa worktree, não na raiz do repo principal

Rode:

```bash
git rev-parse --show-toplevel
git rev-parse --git-dir
```

Se o toplevel for `/home/eliezer/llab/mr-meeseeks-box`, você está na
raiz. **Pare.** Peça ao Rick para rodar `scripts/task-start.sh <id>`
e reiniciar a sessão na worktree criada.

Worktree legítima tem toplevel em
`/home/eliezer/llab/mr-meeseeks-box/.worktrees/<id>-<slug>` e
`git-dir` apontando para `.git/worktrees/<id>-<slug>` da raiz.

### 2. Você não está em `master` (nem `main`)

```bash
git branch --show-current
```

Deve ser `task/<id>-<slug>`. Se for `master` ou `main`, **pare**.
A branch existe pra isolar suas mudanças do tronco.

### 3. Sua branch está alinhada com master

```bash
git fetch origin master --quiet 2>/dev/null || true
git rev-list --count master..HEAD   # commits seus à frente de master
git rev-list --count HEAD..master   # commits de master não presentes aqui
```

- Atrasada (HEAD..master > 0): **pare**, peça ao Rick para
  `git rebase master` na worktree, ou recrie a worktree.
- Adiantada (master..HEAD > 0): ok, são seus commits em progresso.
- Zero/zero: estado fresco, perfeito.

### 4. Working tree limpa antes de começar

```bash
git status --porcelain
```

Vazio = ok. Se tiver mudanças não-commitadas que você não fez
nesta sessão, **pare** e pergunte. Pode ser trabalho anterior em
curso de outro agente que crashou.

## Fluxo de trabalho

Depois de pré-flight verde:

1. **Leia o brief**: `cat docs/tasks/<seu-id>-<slug>.md`. Ele tem
   intenção, escopo, critério de pronto, e decisões em aberto.
2. **Confirme alinhamento** com o Rick se houver decisão em aberto
   no brief.
3. **Trabalhe**. Faça commits pequenos e descritivos no estilo
   `git log` do projeto (`feat: ...`, `fix: ...`, etc.).
4. **Rode os testes locais** antes de cada commit (`.venv/bin/pytest`).
5. **Não mergeie** na master. Só o Rick aprova e mergeia.
6. **Reporte** ao fim: o que foi feito, o que ficou pendente, e
   eventuais decisões que tomou no caminho.

## Convenções

| Item | Convenção |
|---|---|
| Nome da worktree | `.worktrees/<id>-<slug>` (relativo à raiz do MMB) |
| Nome da branch | `task/<id>-<slug>` |
| Base da branch | `master` (sempre) |
| Granularidade de commit | Um conceito atômico por commit. Não acumule. |
| Estilo de commit message | Como os existentes: `feat: ...`, `fix: ...`, `refactor: ...`, `test: ...`, `docs: ...` |
| Hooks | Nunca pule (`--no-verify` é proibido) |
| Push | Não pushe sem o Rick aprovar |

## Coordenação entre agentes paralelos

Se outro agente está atacando uma task com **interseção de arquivos**,
o brief avisa em "Conflito potencial com". Nesse caso:

- Confirme com o Rick antes de começar.
- Aceite que pode ter conflito de merge depois.

Tasks 🎯 listadas como prontas em `INDEX.md` já foram escolhidas
para terem **interseção mínima** entre si (ver matriz de coreografia
em `docs/arvore.md`).

## Quando o brief não cobre alguma situação

A regra: **escopo do brief vence**. Se aparecer algo fora dele que
parece importante (bug paralelo, refactor adjacente, oportunidade),
você NÃO faz. Anota no relatório final e pergunta ao Rick depois.
Mesma régua que a Garagem aplica nos Meeseeks.

## Cleanup ao terminar

Depois do PR mergeado:

```bash
# Volta pra raiz do MMB
cd /home/eliezer/llab/mr-meeseeks-box

# Remove worktree
git worktree remove --force .worktrees/<id>-<slug>

# Apaga branch local (já mergeada)
git branch -d task/<id>-<slug>
```

`scripts/task-end.sh <id>` automatiza isso quando você quiser.
