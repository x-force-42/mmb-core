# Task B1 — Plano de execução

Plano detalhado da execução da B1, complementar ao brief
[`B1-projetos-1a-classe.md`](B1-projetos-1a-classe.md). O brief tem o
**o quê** e o **por quê**; este doc tem o **como** e a **ordem**.

Escrito em 2026-05-14, depois de alinhamento Rick × agente sobre as
decisões em aberto do brief.

## Decisões fechadas

| Decisão | Resolução | Razão |
|---|---|---|
| Soft vs hard delete | **Soft** (coluna `active`) | Preserva integridade referencial com `runs` |
| `/meeseeks` sem `projeto:` | **Erro explícito** — sempre obrigatório | Comportamento previsível, sem mágica |
| `created_by_user_id` | **Fora** desta task | Modelo de identidade ainda não está claro |
| Path tem que ser repo git | **Sim** — validação rejeita se não tiver `.git/` | Critério objetivo, casa com o caso de uso real |
| Cadastro de projeto (UI) | **Minimalista** — `/project add | list | remove` esqueleto funcional | A forma "boa" de cadastro vai ser repensada (provável B3 bootstrap); por ora só precisa funcionar |
| Aquário emite `project` no payload | **NÃO nesta task** | Protocolo WS atual é fechado a campos extras (`aquario/messages.py:11`). A3 coordena o schema novo com o cockpit |

## Filosofia da entrega

> Construir o **core multi-projeto** de forma agnóstica à UI de cadastro.

O foco é a fundação de dados + API. Os comandos Discord existem porque
sem eles não dá pra testar o fluxo ponta-a-ponta, mas são fachada fina
sobre a API do `RunLogger`. Qualquer outra forma futura de cadastrar
projeto (wizard, DM, bootstrap interview da B3, CLI direto, seed via
arquivo) plugaria na mesma API sem refactor.

Anti-padrão consciente: **não** investir em UX de confirmação
interativa, embeds caprichados, mensagens cheias de personalidade pra
o grupo `/project`. Voz Rick & Morty fica nos comandos que já tinham
(`/meeseeks`).

## Arquitetura — camadas

```
┌────────────────────────────────────────────────────────────┐
│ bot.py — handlers Discord                                  │
│   /project add | list | remove  (fachada fina)             │
│   /meeseeks projeto:<slug>      (lookup por slug)          │
│   autocomplete projeto:         (chama list_projects)      │
└────────────────────────────────┬───────────────────────────┘
                                 │ traduz exceção→embed
┌────────────────────────────────▼───────────────────────────┐
│ logger/__init__.py — API estável                           │
│   register_project(...)  ← valida slug/path/git, levanta   │
│   list_projects(include_inactive=False)                    │
│   get_project_by_slug(slug)                                │
│   deactivate_project(slug)                                 │
│   ensure_project(...)    ← mantido por compat, vira thin   │
│                            wrapper de register_project     │
└────────────────────────────────┬───────────────────────────┘
                                 │
┌────────────────────────────────▼───────────────────────────┐
│ logger/_db.py — schema + migração idempotente              │
│   ALTER TABLE projects ADD COLUMN active INTEGER DEFAULT 1 │
│   ALTER TABLE projects ADD COLUMN mode   TEXT NOT NULL …   │
└────────────────────────────────────────────────────────────┘
```

Notas:

- **Validações vivem no logger**, não no handler. Discord só traduz
  exceções tipadas em embeds de erro.
- `ensure_project` permanece com a assinatura atual (chamado pelo
  `on_ready` legado e por testes existentes). Internamente passa a
  delegar pro `register_project`, que tem a validação completa.
- `register_project` levanta `ProjectError` (com subclasses
  `SlugInvalido`, `SlugDuplicado`, `PathInexistente`, `PathNaoEhRepo`).

## Fora de escopo (e onde vai)

| Item | Onde vai |
|---|---|
| Garagem com contexto persistente | B2 |
| Aquário emitir `project` | A3 |
| Modelo diferente por projeto | B3 (interview) ou depois |
| Permissão por Discord user | Task futura ainda não criada |
| Cleanup de worktrees órfãs em projetos removidos | Não vamos fazer (assume disciplinado) |
| Mode `construtor` ter qualquer comportamento | B3 |

A coluna `mode` é armazenada já, mas não influi em nada no fluxo
nesta task. É puro storage pra desbloquear B3 sem nova migração.

## Fases (= sequência de commits)

Ordem pensada pra que cada commit seja revisável isolado e o teste
suite continue verde a cada um.

### Fase 1 — schema + migração idempotente

Arquivo: `logger/_db.py`

- Adiciona ao `_SCHEMA` as colunas `active` e `mode` na tabela
  `projects`. Schema é executado com `IF NOT EXISTS`, então pra DBs
  já criados precisa de migração.
- Em `get_connection`, depois de `executescript(_SCHEMA)`, roda dois
  `ALTER TABLE … ADD COLUMN` tolerantes a `OperationalError` (column
  already exists).

Commit: `feat(logger): adiciona colunas active e mode em projects`

Testes: existem testes do logger que criam DB do zero — devem
continuar verdes. Adiciona 1 teste novo verificando que migração em
DB antigo (sem as colunas) não quebra.

### Fase 2 — API do logger

Arquivo: `logger/__init__.py`

- Cria exceções tipadas: `ProjectError`, `SlugInvalido`,
  `SlugDuplicado`, `PathInexistente`, `PathNaoEhRepo`.
- Cria `register_project(*, slug, path, name=None, mode="pontual",
  repo_url=None) -> dict` (retorna o projeto criado).
  - Valida `slug`: kebab-case, ≤30 chars, regex `^[a-z][a-z0-9-]*$`.
  - Valida `path`: existe, é diretório, contém `.git/`.
  - Valida `mode`: `"pontual"` ou `"construtor"`.
  - `name` default = `slug`.
  - Levanta `SlugDuplicado` se já existe (ativo ou inativo —
    decisão: reaproveitar slug inativo é manual via reativação
    futura; nesta task simplificamos: slug é único globalmente).
- `list_projects(*, include_inactive=False)` — atualiza método
  atual pra filtrar por `active=1` por default.
- `get_project_by_slug(slug) -> dict | None` — novo, conveniência.
- `deactivate_project(slug) -> bool` — seta `active=0`. Retorna
  `False` se slug não existe ou já estava inativo.
- `ensure_project` continua existindo — internamente delega pro
  `register_project` (com `try/except SlugDuplicado: pass` pra
  manter a semântica upsert idempotente que ele tinha).

Commit: `feat(logger): API de projetos com validação centralizada`

Testes novos:
- `test_register_project_kebab_case_invalido`
- `test_register_project_path_inexistente`
- `test_register_project_path_nao_git`
- `test_register_project_slug_duplicado`
- `test_list_projects_exclui_inativos_por_default`
- `test_list_projects_include_inactive_traz_tudo`
- `test_deactivate_project_idempotente`
- `test_get_project_by_slug`
- `test_ensure_project_ainda_funciona` (não-regressão)

### Fase 3 — `TARGET_PROJECT_PATH` opcional + seed migracional

Arquivo: `config.py` e `bot.py`

- `config.py`: `TARGET_PROJECT_PATH` deixa de levantar erro se
  faltar/não existir. Vira `Path | None`. Mantém o nome (não
  renomeia) pra evitar churn.
- `bot.py` `on_ready`: depois do `_logger` instanciado, se
  `_logger.list_projects()` é vazio E `TARGET_PROJECT_PATH` está
  setado E existe, faz seed:
  `_logger.ensure_project(slug=TARGET_PROJECT_PATH.name,
   name=TARGET_PROJECT_PATH.name, path=str(TARGET_PROJECT_PATH))`.
  Loga `[migração] projeto default registrado: <slug>`.

Commit: `refactor(config): TARGET_PROJECT_PATH vira opcional`
+ um commit junto ou separado pro seed (avalio na hora).

Testes: ajuste de fixtures que dependiam de `TARGET_PROJECT_PATH`
ser obrigatório. Adiciona teste do seed no `on_ready` (mockado).

### Fase 4 — comandos Discord `/project`

Arquivo: `bot.py`

- Cria `project_group = app_commands.Group(name="project", description="Gerenciar projetos do MMB")`.
- `/project add path slug [name] [mode]`:
  - Chama `_logger.register_project(...)`.
  - Em caso de exceção `ProjectError`, monta embed de erro claro
    (nome do erro + sugestão).
  - Em caso de sucesso, embed simples com slug + path + mode.
- `/project list`:
  - Chama `_logger.list_projects()`.
  - Embed com tabela: slug | mode | path | criado.
  - Trunca em 25 linhas (limite do Discord embed). Se passar,
    nota no rodapé "+N projetos não exibidos".
- `/project remove slug`:
  - Chama `_logger.deactivate_project(slug)`.
  - Embed simples confirmando ou avisando "slug não encontrado".
  - Sem confirmação interativa (anti-padrão consciente — UX
    mínima).
- `client.tree.add_command(project_group)` no setup.

Commit: `feat(bot): comandos /project add | list | remove`

Embeds: dois novos em `embeds.py`: `embed_project_ok(...)` e
`embed_project_erro(titulo, descricao)`. Reutilizar paleta existente.

Testes: `tests/unit/test_bot_projects.py` (novo). Mocka
`discord.Interaction` e `_logger`. Cobre os 3 handlers.

### Fase 5 — `/meeseeks` resolve projeto por slug

Arquivo: `bot.py` (e provavelmente `pipeline.py`)

- Adiciona parâmetro `projeto: str` no `/meeseeks`. Required no
  Discord side (sem default → o Discord exige).
- Adiciona autocomplete: handler `project_autocomplete(interaction,
  current)` que retorna até 25 choices filtrados pelo `current`.
- No handler: resolve `_logger.get_project_by_slug(projeto)`. Se
  None → embed de erro pedindo `/project list`.
- O path resolvido substitui o uso atual de `TARGET_PROJECT_PATH`
  na chamada `invocar_garagem(task, project_path)` e nas chamadas
  subsequentes do pipeline. **Não tocar mais `TARGET_PROJECT_PATH`
  fora do seed migracional.**
- `start_run` passa a usar `project_id` do projeto resolvido (já
  fazia, mas via `ensure_project` no `on_ready`; agora vem do
  lookup runtime).

Commit: `feat(bot): /meeseeks resolve projeto por slug em runtime`

Testes: atualizar testes existentes do `/meeseeks` pra passar
`projeto=` + lookup. Adiciona teste de erro pra slug inexistente
e teste do autocomplete.

### Fase 6 — sweep de testes legados

Vários testes assumem `TARGET_PROJECT_PATH` setado e único. Os
ajustes provavelmente são:

- Fixtures que setavam `TARGET_PROJECT_PATH` no env passam a
  registrar projeto no logger fixture.
- `test_api_projects.py` (existe) — checar se quer expor `active`
  e `mode` na API ou se filtra. Default: API retorna só ativos.

Commit: `test: atualiza fixtures pra modelo multi-projeto`

## Sobre o aquário (e por que não mexer)

O brief original (linha 75) diz "Aquário emite `project` no payload —
task A3 puxa esse dado daqui." Aparentemente a intenção era B1
emitir, A3 consumir.

Mas: `aquario/messages.py:1-13` é explícito que o protocolo é fechado
e o consumer dropa payload com campos extras. Adicionar `project` no
WS sem coordenar com o cockpit quebra o cockpit silenciosamente.

Decisão: aquário fica intacto. Bot sabe o projeto, mas eventos WS
continuam `(id, name, task)`. A A3 é justamente "aquário
multi-projeto" — ela trata schema novo, coordena release com o
cockpit, e usa o `project_id` que já vai estar no `RunLogger` desde
esta task.

Persistência: o `project_id` do run **já é gravado** no banco em
`runs` (sempre foi — vide `start_run`). Esse é o ponto de
integração suficiente. A3 lê do banco, não do WS.

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Testes legados acumulam quebra silenciosa | Fase 1-3 não toca handler do `/meeseeks`; rodar suite a cada commit |
| `ensure_project` muda semântica e quebra `on_ready` antigo | Wrapper que silencia `SlugDuplicado` mantém comportamento upsert |
| Race condition em validação de path durante `register_project` | Aceito — best-effort. Se path some entre validar e registrar, o run posterior falha com erro claro |
| Slug colidir com slug inativo | Decisão: slug é único globalmente. Reativação fica pra task futura |
| Migração de DB em produção (`mmb.db` existente) falhar | ALTER tolerante a `OperationalError`, idempotente. Teste cobre |

## Estimativa atualizada

Brief original disse 3-5 dias. Com a UI minimalista (sem confirmação
interativa, sem polish de embed) e sem mexer no aquário, estimo
**2-3 dias** de trabalho focado, divididos:

- Fase 1+2: meio dia (puro logger, testes incluídos)
- Fase 3: 2 horas
- Fase 4: meio dia (3 handlers + embeds + testes)
- Fase 5: meio dia (handler do `/meeseeks` + autocomplete + testes)
- Fase 6: 2-4 horas (sweep de fixtures)

## Critério de pronto (espelha brief, com ajustes)

1. `/project add` aceita path+slug+mode, valida git, cria projeto.
2. `/project list` retorna projetos ativos (ou todos se flag).
3. `/project remove` faz soft delete.
4. `/meeseeks projeto:<slug>` resolve via logger, passa o path.
5. Sem `projeto:` → erro do Discord ("missing required argument") OU
   embed nosso se chegar. **Sem fallback.**
6. Autocomplete funciona.
7. Migração: `mmb.db` existente com `TARGET_PROJECT_PATH` configurado
   e tabela `projects` ainda sem `active`/`mode` faz upgrade limpo.
8. Suite antiga verde.
9. ≥6 testes novos (na prática ~12 contando os do logger e dos
   handlers Discord).
10. Aquário não mudou. A3 pega o trabalho a partir do `project_id`
    persistido em `runs`.
