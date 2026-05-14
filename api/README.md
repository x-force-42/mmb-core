# MMB Cockpit API

API REST que alimenta o **Cockpit de Operações** — um dashboard
(em repo separado, `~/llab/mmb-cockpit`) onde o Rick acompanha
runs, custos e qualidade do MMB.

Camada thin sobre o `logger/` SDK. Read-only na maior parte; só
`PATCH /api/runs/{id}` escreve (e só nos 3 campos manuais de
review).

## Por que processo separado

Lifecycle independente do bot:

- Cockpit funciona mesmo com `bot.py` parado (visualiza histórico).
- Bot funciona mesmo com a API parada (não depende dela pra rodar).

Compartilham só o arquivo SQLite (`MMB_DB_PATH`). Mesma filosofia
"side car observável" do `logger/`.

## Subindo

```bash
scripts/api.sh
```

Por padrão escuta em `http://localhost:8765`. Overrides:

| Env | Default | Função |
|---|---|---|
| `MMB_API_PORT` | `8765` | Porta de escuta. |
| `MMB_API_CORS_ORIGINS` | `http://localhost:5173` | Origens permitidas (CSV). |
| `MMB_DB_PATH` | `mmb.db` | Banco compartilhado com o bot. |

Docs interativas em `http://localhost:8765/docs` (Swagger UI) e
`http://localhost:8765/redoc`.

## Endpoints

### `GET /api/runs`

Lista paginada com filtros opcionais.

Query params:

| Param | Tipo | Default | Função |
|---|---|---|---|
| `project` | slug | — | Filtra por projeto. |
| `phase` | enum | — | `success`, `meeseeks_failure`, `dev_server_failure`, `garagem_pushback`, `garagem_no_slug`, `garagem_error`. |
| `from` | ISO date | — | Janela inicial sobre `started_at`. |
| `to` | ISO date | — | Janela final sobre `started_at`. |
| `limit` | int | 50 | Cap em 200. |
| `offset` | int | 0 | — |
| `order` | enum | `started_at:desc` | `started_at:asc|desc`, `total_elapsed_s:asc|desc`. |

```bash
curl 'http://localhost:8765/api/runs?phase=success&limit=10'
```

Devolve `{items: [...], total, limit, offset}`.

### `GET /api/runs/{id}`

Detalhe completo. `garagem_briefing_json` e `meeseeks_commits_json`
saem já parseados (não como string). 404 se id não existe.

### `PATCH /api/runs/{id}`

Atualiza os 3 campos de review manual:

```bash
curl -X PATCH http://localhost:8765/api/runs/<id> \
  -H 'content-type: application/json' \
  -d '{
    "merged_to_main": 1,
    "assertiveness_score": 4,
    "review_note": "ficou bom, só o estilo do commit que destoou"
  }'
```

Validação:

- `merged_to_main`: `0`, `1` ou `null`.
- `assertiveness_score`: `1`–`5` ou `null`.
- `review_note`: string ou `null`.

Campos fora desses 3 são silenciosamente ignorados (não é erro).
Devolve o run completo atualizado.

### `GET /api/projects`

Lista todos os projetos cadastrados. Sem paginação (volume é
dezenas, não milhares).

### `GET /api/metrics/overview?days=N`

Agregados para o dashboard de governança. `days` default 30.

```json
{
  "window_days": 30,
  "runs_total": 87,
  "custo_total_usd": 4.23,
  "tempo_medio_s": 92.1,
  "taxa_pushback": 0.18,
  "custo_por_dia": [{"dia": "2026-05-14", "usd": 0.45}, ...],
  "runs_por_dia": [{"dia": "2026-05-14", "n": 12}, ...],
  "phase_breakdown": {"success": 60, "meeseeks_failure": 12, ...}
}
```

Dias zero não vêm preenchidos — frontend decide como plotar.

## CORS

Sem auth (é localhost). CORS limitado a `MMB_API_CORS_ORIGINS` —
default casa com Vite (`http://localhost:5173`).

## Testes

```bash
.venv/bin/pytest tests/unit/test_api*.py -v
```
