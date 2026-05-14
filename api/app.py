"""FastAPI app do Cockpit de Operações.

Localhost-only por design — sem auth, sem rate limit. Confia no
operador. Roda em processo separado do bot; compartilha só o SQLite.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from api.routes import metrics, projects, runs

_DESCRIPTION = """
API REST que alimenta o **Cockpit de Operações** do MMB (Mr. Meeseeks Box).

Camada thin sobre o `logger/` SDK — expõe runs, projetos e métricas
agregadas em JSON. Read-only na maior parte; só `PATCH /api/runs/{id}`
escreve, e apenas nos 3 campos manuais de review.

### Arquitetura

Processo separado do bot do Discord. Compartilham só o arquivo SQLite
(`MMB_DB_PATH`). Cockpit funciona com bot parado e vice-versa.

### Sem auth

Localhost-only por design. CORS limitado a `MMB_API_CORS_ORIGINS`
(default `http://localhost:5173`).
"""

_TAGS = [
    {
        "name": "runs",
        "description": "Histórico de runs do `/meeseeks`. Listagem com filtros, "
                       "detalhe completo e PATCH dos campos de review manual.",
    },
    {
        "name": "projects",
        "description": "Projetos-alvo cadastrados (cada slug = uma pasta no disco).",
    },
    {
        "name": "metrics",
        "description": "Agregados para o dashboard de governança "
                       "(custo, taxa de pushback, séries diárias).",
    },
    {
        "name": "meta",
        "description": "Endpoints utilitários da própria API.",
    },
]

app = FastAPI(
    title="MMB Cockpit API",
    description=_DESCRIPTION,
    version="0.1.0",
    openapi_tags=_TAGS,
    contact={"name": "Rick (mantenedor)"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.MMB_API_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(runs.router)
app.include_router(projects.router)
app.include_router(metrics.router)


@app.get(
    "/",
    tags=["meta"],
    summary="Service descriptor",
    description="Identifica a API e lista os endpoints disponíveis. "
                "Útil pra health-check leve.",
)
def root() -> dict:
    return {
        "service": "mmb-cockpit-api",
        "version": app.version,
        "endpoints": [
            "GET /api/runs",
            "GET /api/runs/{id}",
            "PATCH /api/runs/{id}",
            "GET /api/projects",
            "GET /api/metrics/overview",
        ],
    }
