# Task B1 — Projetos como cidadão de 1ª classe

## ID
B1

## Trilha
B — Plataforma

## Status
🎯 pronto pra delegar

## Intenção

Hoje o MMB opera contra **um único** projeto fixado em
`TARGET_PROJECT_PATH` no `.env`. A virada estratégica documentada
em `docs/arvore.md` é virar **plataforma multi-projeto**: o Rick
cadastra N projetos, lança tarefas via Discord especificando qual,
um Meeseeks por projeto roda isolado.

Esta task é a fundação. Remove o conceito de "alvo único", introduz
o registro de projetos como entidade gerenciável via Discord, e
adapta o pipeline pra fazer lookup dinâmico do projeto em cada
invocação do `/meeseeks`.

A tabela `projects` no SQLite **já existe** (Ato VI) e já é
populada via `ensure_project` no `on_ready`. Esta task transforma
essa tabela de "side effect informativo" em "registro autoritativo
consultado em runtime".

## Escopo

### Dentro
- Comando Discord `/project` com subcomandos:
  - `/project add path:<absolute_path> slug:<short_name>
    [name:<display>]`
  - `/project list`
  - `/project remove slug:<short_name>` (soft delete ou hard? ver
    decisões)
- `/meeseeks` ganha parâmetro `projeto: str` (autocomplete via
  slash command autocomplete API do discord.py).
- `bot.py` faz lookup do projeto em runtime: ao invocar
  `invocar_garagem`/`invocar_meeseeks`, passa o `path` registrado
  pra aquele slug. **Não toca mais `TARGET_PROJECT_PATH`**.
- `config.py`: `TARGET_PROJECT_PATH` vira **opcional**, usado só
  como migração — se setado e tabela `projects` vazia no
  `on_ready`, registra ele como projeto default.
- Validação: comando `/project add` rejeita paths que não
  existem ou não são repos git, slugs duplicados, slugs
  inválidos (kebab-case, ≤30 chars).
- Mensagens de status do bot incluem qual projeto (no embed do
  `embed_garagem_working` etc).

### Fora
- Garagem com contexto persistente — task B2.
- Aquário emite `project` no payload — task A3 puxa esse dado
  daqui.
- Modelo diferente por projeto — task B3.
- Permissão por projeto (qual user Discord pode mexer em qual
  projeto). Por enquanto qualquer um pode tudo.

## Critério de pronto

1. `/project add path:/home/eliezer/vnt/ASUS/jogo slug:jogo` é
   aceito, cria linha em `projects` se não existia, retorna
   embed confirmando.
2. `/project list` retorna embed com tabela de projetos: slug,
   nome, path, criado em. Discord pode aceitar até ~25 linhas.
3. `/project remove slug:jogo` remove (ver decisão soft/hard
   abaixo). Confirmação interativa via reaction ou button
   recomendada.
4. `/meeseeks projeto:jogo task:...` funciona ponta-a-ponta como
   antes, mas com projeto vindo do registro.
5. Sem `projeto:`: comportamento configurável. Default sugerido:
   se só tem 1 projeto registrado, usa ele. Se tem mais, retorna
   erro pedindo pra especificar.
6. Autocomplete do parâmetro `projeto:` lista slugs registrados.
7. Migração: instância existente com `TARGET_PROJECT_PATH` e
   tabela `projects` vazia continua funcionando após upgrade.
   `on_ready` faz o seed do projeto default.
8. 192 testes unit/integration antigos continuam verdes (alguns
   provavelmente vão precisar de update — `ensure_project` muda
   semântica).
9. Pelo menos 6 testes novos:
   - `add` cria
   - `add` rejeita slug duplicado
   - `add` rejeita path inexistente
   - `list` retorna projetos
   - `remove` apaga
   - `meeseeks` resolve projeto pelo slug

## Contexto técnico

### Arquivos relevantes
- `bot.py` — handler atual de `/meeseeks`. Cuide do parâmetro
  novo e da resolução do path.
- `config.py` — `TARGET_PROJECT_PATH` deixa de ser obrigatório,
  vira hint de migração.
- `logger/__init__.py` — `ensure_project`, `get_project` já
  existem. Pode precisar adicionar `list_projects` e `delete_project`.
- `logger/_db.py` — schema da tabela `projects`. Pode precisar
  adicionar coluna `active BOOLEAN DEFAULT 1` se for soft delete.
- `embeds.py` — embeds existentes ganham o nome do projeto. Pode
  fazer sentido criar `embed_project_added`, `embed_project_list`.

### Padrões do projeto
- Slash commands seguem o padrão de `/meeseeks` em `bot.py`. Use
  `@app_commands.describe` pra descrição dos parâmetros.
- Embeds com a paleta em `embeds.py` (existem `cor_garagem`,
  `cor_meeseeks`, etc).
- Cleanup: dados orfãos (worktrees em projetos removidos) não
  vamos limpar nesta task — assume disciplinado.

## Implementação sugerida

### Schema do DB

Adicionar coluna `active INTEGER DEFAULT 1` em `projects`.
Use uma migração simples no `get_connection`:

```python
def get_connection(path):
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    # migração idempotente
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN active INTEGER DEFAULT 1")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # já existe
    ...
```

Soft delete (recomendado): `delete_project` seta `active=0` em
vez de DELETE. Histórico de runs preserva referência.

### API do RunLogger

```python
def list_projects(self, *, include_inactive=False) -> list[dict]: ...
def get_project_by_slug(self, slug: str) -> dict | None: ...
def deactivate_project(self, slug: str) -> bool: ...
```

### Comandos Discord

```python
project_group = app_commands.Group(name="project", description="...")

@project_group.command()
@app_commands.describe(path="...", slug="...", name="...")
async def add(interaction, path: str, slug: str, name: str = ""):
    ...

@project_group.command()
async def list(interaction):
    ...

@project_group.command()
async def remove(interaction, slug: str):
    ...

client.tree.add_command(project_group)
```

Pra autocomplete em `/meeseeks`:

```python
async def project_autocomplete(interaction, current: str):
    projects = _logger.list_projects()
    return [
        app_commands.Choice(name=p["slug"], value=p["slug"])
        for p in projects
        if current.lower() in p["slug"].lower()
    ][:25]

@app_commands.autocomplete(projeto=project_autocomplete)
async def meeseeks(interaction, task: str, projeto: str = ""):
    ...
```

### Migração

No `on_ready`, depois de `_logger` instanciado:

```python
projects = _logger.list_projects()
if not projects and TARGET_PROJECT_PATH and TARGET_PROJECT_PATH.exists():
    _logger.ensure_project(
        slug=TARGET_PROJECT_PATH.name,
        name=TARGET_PROJECT_PATH.name,
        path=str(TARGET_PROJECT_PATH),
    )
    print(f"[migração] projeto default registrado: {TARGET_PROJECT_PATH.name}")
```

## Testes a adicionar

`tests/unit/test_logger.py`:
- `test_list_projects_excludes_inactive`
- `test_deactivate_project_idempotent`
- `test_get_project_by_slug`

`tests/unit/test_bot_projects.py` (novo):
- Mocks no `_logger.list_projects` + `discord.Interaction`. Testa
  o handler `/project add` aceita, rejeita path inexistente,
  rejeita slug duplicado.
- O resto via mocks similares aos que já existem em outros testes.

E2E: opcional, mas seria show um cenário em `tests/e2e/scenarios/`
que registra um projeto, lança meeseeks, valida.

## Decisões em aberto

1. **Soft vs hard delete** — recomendo soft (preserva integridade
   referencial com `runs`). Confirme com o Rick.
2. **Comportamento sem `projeto:`** — sugerido: se 1 projeto,
   usa ele; senão, erro. Alternativa: sempre exigir o parâmetro.
   **Default sugerido fica até o Rick discordar.**
3. **Permissionamento por user Discord** — fora de escopo nesta
   task, mas vai ser necessário em algum momento. Vale considerar
   se a coluna `created_by_user_id` deveria já entrar agora.
4. **Validação de path** — exigir `.git/` no path (deve ser repo
   git)? Recomendo sim.

## Dependências
- Bloqueia: A3, B2. Ambas precisam de `projects` como entidade
  autoritativa.
- Bloqueado por: idealmente A1 deveria estar mergeada (ambas
  tocam `bot.py` muito). Mas roda standalone se aceitar conflito
  de merge.

## Conflito potencial com
**A1**. Ambos tocam `bot.py` em `on_ready` e nos handlers de
slash command. Ver matriz em `INDEX.md`. Recomendação: A1 primeiro.

## Estimativa
~3-5 dias. Maior risco é a UX dos comandos Discord (autocomplete,
embeds bonitos) e a migração suave. O DB layer é trivial.
