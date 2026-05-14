# Task E1 — API do Cockpit de Operações

## ID
E1

## Trilha
E — Cockpit de Operações

## Status
🎯 pronto pra delegar — discovery fechado em E0

## Intenção

Construir a **API REST que alimenta o Cockpit de Operações** —
camada thin sobre o `logger/` SDK, expondo runs, projetos e
métricas agregadas em formato JSON. Read-only na maior parte;
`PATCH` apenas pros 3 campos manuais de review (`merged_to_main`,
`assertiveness_score`, `review_note`).

A API roda em **processo separado** do bot — independência de
lifecycle: cockpit funciona mesmo quando o bot está fora do ar,
e vice-versa. Ambos compartilham só o arquivo SQLite.

Mesma filosofia "side car observável" do `logger/` e do
(futuro) `aquario/`: zero acoplamento com `bot.py`/`garagem.py`/
`meeseeks.py`.

## Escopo

### Dentro

- Novo módulo `api/` no MMB, com FastAPI app:
  - `api/__init__.py` — exporta `app`.
  - `api/app.py` — FastAPI() + CORS + startup que abre conexão
    read-friendly ao SQLite.
  - `api/models.py` — Pydantic v2 schemas pra request/response.
  - `api/routes/runs.py` — `GET /api/runs`, `GET /api/runs/{id}`,
    `PATCH /api/runs/{id}`.
  - `api/routes/projects.py` — `GET /api/projects`.
  - `api/routes/metrics.py` — `GET /api/metrics/overview`.
- 5 endpoints conforme decisões fechadas no E0 (vide "Contrato"
  abaixo).
- CORS habilitado pra `http://localhost:5173` (Vite default do
  cockpit). Sem auth — é localhost.
- Config via `.env`: `MMB_API_PORT` (default `8765`),
  `MMB_API_CORS_ORIGINS` (default `http://localhost:5173`,
  formato CSV pra suportar várias origens em dev se necessário).
- `scripts/api.sh` — entrypoint dedicado tipo `e2e.sh`. Roda
  `.venv/bin/uvicorn api.app:app --port <MMB_API_PORT> --reload`.
- Adicionar `fastapi`, `uvicorn[standard]`, `pydantic` ao
  `requirements.txt` (criar se não existir — projeto hoje não tem
  arquivo formal de deps).
- Testes unitários cobrindo cada endpoint via `TestClient` do
  FastAPI, banco em `tmp_path/test_api.db`.

### Fora

- Frontend / cockpit em si. Vive em repo separado futuro
  (`~/llab/mmb-cockpit`). Esta task entrega só a API.
- Auth, rate limiting, observabilidade da própria API. Não há
  necessidade em localhost.
- Endpoints para v2 (catálogo detalhado de projetos com runs
  agregadas, comparativo de modelos, garagem-context). Adicionados
  conforme B1/B2/B3 entregarem schema.
- Push em tempo real (WebSocket). Cockpit MVP é pull/refresh.
- Versionamento de API (`/api/v1/...`). Mantemos `/api/...` flat;
  introduzimos versionamento quando houver primeira quebra real.
- Migrações de schema do SQLite. Só lê o schema atual definido
  em `logger/_db.py`.

## Critério de pronto

1. `scripts/api.sh` sobe o servidor em `localhost:8765` sem erro.
2. `curl http://localhost:8765/api/runs` retorna JSON com runs
   reais do `mmb.db` (se existir; senão lista vazia válida).
3. Os 5 endpoints especificados em "Contrato" abaixo respondem
   com 200 + payload no formato esperado, e com códigos de erro
   apropriados (404 pra run inexistente, 422 pra body inválido
   no PATCH, etc).
4. `PATCH /api/runs/{id}` persiste os 3 campos e ignora qualquer
   outro campo no body (não permite editar `task_raw`, `commits`,
   etc — só os 3 manuais).
5. CORS respondendo corretamente quando o cockpit (rodando em
   `localhost:5173`) bate. Validado com `curl -H "Origin: http://localhost:5173"`.
6. Testes unitários verdes:
   `.venv/bin/pytest tests/unit/test_api*.py -v`.
   Cobertura: pelo menos 1 teste por endpoint, mais 2-3 testes
   de erro (404, 422, filtros combinados).
7. README curto em `api/README.md` (ou seção em README.md raiz)
   explicando como subir e os endpoints disponíveis.
8. Bot continua funcional sem a API rodando (e vice-versa).
   Smoke: parar a API, rodar `/meeseeks`, confirmar que segue.

## Contexto técnico

### Arquivos relevantes

- `logger/__init__.py` — `RunLogger` com `get_run`, `get_project`.
  Falta `list_runs` (com filtros), `list_projects`, métricas
  agregadas. **Adicionar esses métodos no `RunLogger` em vez de
  duplicar SQL na camada da API.** Reuso direto.
- `logger/_db.py` — schema da tabela `runs` e `projects`. **Não
  altere o schema** nesta task — só lê. Migrações ficam pra
  outras tasks (B1, etc).
- `config.py` — onde adicionar `MMB_API_PORT` e `MMB_API_CORS_ORIGINS`.
- `pyproject.toml` — config de pytest. Pode precisar ajustar
  `testpaths` se adicionar nova subpasta de testes (provavelmente
  não, `tests/unit/` já cobre).

### Padrões do projeto

- Português brasileiro em strings de erro voltadas ao usuário /
  comentários. Inglês em nomes de campo da API (cobertos pelo
  schema existente).
- Funções puras testáveis isoladas do IO quando possível (ex.
  agregação de métricas pode ter helper puro `_aggregate_overview`
  que recebe linhas e devolve dict; o endpoint só plumbing).
- Mesma estética dos módulos vizinhos (`logger/`, `aquario/`
  futuro): pequeno, sem deps pesadas além do framework.
- `print("[warn] ...")` pra logging defensivo — não introduza
  `logging` stdlib só pra essa task.

### Contrato dos 5 endpoints

#### `GET /api/runs`

Lista paginada com filtros opcionais.

Query params:
- `project` (string, slug) — filtra por projeto.
- `phase` (string) — filtra por `terminal_phase`. Valores válidos:
  `success`, `meeseeks_failure`, `dev_server_failure`,
  `garagem_pushback`, `garagem_no_slug`, `garagem_error`.
- `from`, `to` (ISO date `YYYY-MM-DD`) — janela temporal sobre
  `started_at`.
- `limit` (int, default 50, max 200).
- `offset` (int, default 0).
- `order` (string, default `started_at:desc`). Aceita
  `started_at:asc|desc`, `total_elapsed_s:asc|desc`.

Response 200:

```json
{
  "items": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "project_slug": "jogo",
      "started_at": "2026-05-14T...",
      "task_raw": "...",
      "terminal_phase": "success",
      "total_elapsed_s": 87.4,
      "garagem_outcome": "success",
      "garagem_cost_usd": 0.02,
      "meeseeks_outcome": "success",
      "meeseeks_cost_usd": 0.08,
      "merged_to_main": null,
      "assertiveness_score": null
    }
  ],
  "total": 142,
  "limit": 50,
  "offset": 0
}
```

Campos do item são uma projeção enxuta — o suficiente pra a tela
de lista. Detalhe completo só em `GET /api/runs/{id}`.

#### `GET /api/runs/{id}`

Detalhe completo.

Response 200: todos os campos da tabela `runs` + `project_slug`
joinado + `briefing_json` parseado (já como objeto JSON, não
string). Campos `meeseeks_commits_json` idem.

Response 404 se id inexistente:
```json
{"detail": "run não encontrado"}
```

#### `PATCH /api/runs/{id}`

Atualiza apenas os 3 campos manuais. Outros campos no body são
**ignorados** (não retorna erro, só não persiste — aceitar é mais
gentil que recusar).

Body:
```json
{
  "merged_to_main": 1,
  "assertiveness_score": 4,
  "review_note": "ficou bom, só o estilo do commit que destoou"
}
```

Validação Pydantic:
- `merged_to_main`: `0 | 1 | null`.
- `assertiveness_score`: `1 | 2 | 3 | 4 | 5 | null`.
- `review_note`: `str | null`.

Response 200: retorna o run completo atualizado (mesmo schema do
`GET /api/runs/{id}`). 404 se id inexistente. 422 se valores
fora do domínio.

#### `GET /api/projects`

Lista todos os projetos cadastrados.

Response 200:
```json
{
  "items": [
    {
      "id": "uuid",
      "slug": "jogo",
      "name": "jogo",
      "path": "/home/eliezer/vnt/ASUS/jogo",
      "repo_url": null,
      "created_at": "2026-05-13T..."
    }
  ]
}
```

Sem paginação. Volume esperado é dezenas, não milhares.

#### `GET /api/metrics/overview`

Agregados para o dashboard de governança.

Query params:
- `days` (int, default 30). Janela retroativa.

Response 200:
```json
{
  "window_days": 30,
  "runs_total": 87,
  "custo_total_usd": 4.23,
  "tempo_medio_s": 92.1,
  "taxa_pushback": 0.18,
  "custo_por_dia": [
    {"dia": "2026-05-14", "usd": 0.45},
    {"dia": "2026-05-13", "usd": 0.32}
  ],
  "runs_por_dia": [
    {"dia": "2026-05-14", "n": 12},
    {"dia": "2026-05-13", "n": 7}
  ],
  "phase_breakdown": {
    "success": 60,
    "meeseeks_failure": 12,
    "garagem_pushback": 15
  }
}
```

`custo_por_dia` e `runs_por_dia` ordenados desc por dia. Inclui só
dias com runs (dias zero não preenchidos — frontend decide se
plota como vazio).

## Implementação sugerida

### Adição ao `RunLogger`

Antes de escrever a API, expanda o SDK do logger com os métodos
de leitura que faltam. Mantém a API enxuta (só plumbing) e
reusável fora dela:

```python
def list_runs(
    self, *,
    project_slug: str | None = None,
    phase: str | None = None,
    from_iso: str | None = None,
    to_iso: str | None = None,
    limit: int = 50,
    offset: int = 0,
    order: str = "started_at:desc",
) -> tuple[list[dict], int]:
    """Devolve (items, total). Items são dicts da linha do DB
    com `project_slug` joinado."""

def list_projects(self) -> list[dict]: ...

def update_run_review(
    self, run_id: str, *,
    merged_to_main: int | None,
    assertiveness_score: int | None,
    review_note: str | None,
) -> bool:
    """Retorna True se atualizou (id existe), False senão."""

def overview_metrics(self, *, days: int = 30) -> dict:
    """Calcula agregados via SQL único quando possível."""
```

Testes desses métodos em `tests/unit/test_logger.py` (já existe).

### Estrutura da API

```
api/
├── __init__.py        # expõe `app` (mesmo padrão de logger/)
├── app.py             # FastAPI() + CORS + startup
├── models.py          # Pydantic schemas
├── deps.py            # Depends(get_logger)
└── routes/
    ├── __init__.py
    ├── runs.py
    ├── projects.py
    └── metrics.py
```

`deps.py`: factory do `RunLogger` reusando `MMB_DB_PATH` do
`config.py`. Singleton — mesmo conn pool entre requests.

### Tests

```
tests/unit/test_api_runs.py
tests/unit/test_api_projects.py
tests/unit/test_api_metrics.py
```

Pattern por arquivo:

```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "test_api.db"
    monkeypatch.setattr(config, "MMB_DB_PATH", db)
    # popular DB de teste com 2-3 runs e 1 projeto
    from api.app import app
    return TestClient(app)

def test_list_runs_returns_pagination(client):
    r = client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert body["limit"] == 50
```

Cobertura sugerida (não exaustiva):

- `test_api_runs.py`:
  - lista vazia retorna estrutura correta.
  - lista com 3 runs + filtro por phase reduz corretamente.
  - filtro por `from`/`to` filtra.
  - filtro por `project` filtra.
  - `limit`/`offset` paginar.
  - `GET /api/runs/{id}` 200 + parse do briefing_json.
  - `GET /api/runs/{id}` 404 pra id inexistente.
  - `PATCH /api/runs/{id}` aceita os 3 campos, ignora extras.
  - `PATCH` 422 pra `assertiveness_score=6`.
  - `PATCH` 404 pra id inexistente.

- `test_api_projects.py`: lista com 2 projetos, ordenação.

- `test_api_metrics.py`:
  - estrutura do payload com `days=30`.
  - `runs_por_dia` agrega corretamente.
  - taxa_pushback calculada corretamente.

### Script de subida

`scripts/api.sh`:

```bash
#!/usr/bin/env bash
# Sobe a API do cockpit na porta de MMB_API_PORT (default 8765).
# Compartilha o SQLite com o bot — pode rodar simultâneo.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${MMB_API_PORT:-8765}"
exec .venv/bin/uvicorn api.app:app --port "$PORT" --reload "$@"
```

Permissão de execução (`chmod +x`).

## Testes a adicionar

Já listados acima. Sumário:

- 4-5 testes em `tests/unit/test_logger.py` cobrindo os métodos
  novos (`list_runs`, `list_projects`, `update_run_review`,
  `overview_metrics`).
- ~10 testes em `tests/unit/test_api_*.py` cobrindo os 5
  endpoints + erros.

Meta: manter cobertura ≥85% no `api/` e `logger/`.

## Decisões em aberto
Nenhuma. Tudo fechado no E0.

## Dependências

- Bloqueia: implementação do cockpit em si (repo separado futuro
  `~/llab/mmb-cockpit`).
- Bloqueado por: nada. Roda em paralelo com A1 e qualquer outra
  task (vide conflito potencial abaixo).

## Conflito potencial com

- **A1** (aquário): ✅ sem conflito. A1 toca `aquario/` + hooks em
  `bot.py`. E1 cria `api/`, não toca `bot.py`.
- **B1** (projetos 1ª classe): ⚠️ tocar `logger/__init__.py` e
  `logger/_db.py` em ambos. **Não rodar em paralelo com B1**.
  Recomendo: E1 primeiro (mais leve), depois B1 estende
  `list_projects` se necessário (`active=true` etc).
- **A2/A3/B2/B3/C3/C4**: ✅ sem conflito.

## Estimativa

~2-3 dias. Distribuição:

- Métodos novos no `RunLogger` + testes: ~0.5d.
- FastAPI app + routes + Pydantic models: ~0.5d.
- Testes da API: ~0.5d.
- CORS + scripts/api.sh + README + smoke local: ~0.5d.
- Buffer pra ajustes e revisão: ~0.5-1d.
