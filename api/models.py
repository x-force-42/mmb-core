"""Pydantic schemas pra request/response da API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ─── runs ────────────────────────────────────────────────────────────────


class RunListItem(BaseModel):
    """Projeção enxuta — suficiente pra a tela de lista do cockpit."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "9b1f7e22-1c4d-4e1a-92aa-7c0b6e5b3a01",
            "project_id": "2a3d9f60-b2b1-4f0a-9c11-1d2e3f4a5b6c",
            "project_slug": "jogo",
            "started_at": "2026-05-14T18:42:11+00:00",
            "task_raw": "ajusta cor do botão de start",
            "terminal_phase": "success",
            "total_elapsed_s": 87.4,
            "garagem_outcome": "success",
            "garagem_cost_usd": 0.02,
            "meeseeks_outcome": "success",
            "meeseeks_cost_usd": 0.08,
            "merged_to_main": 1,
            "assertiveness_score": 4,
        }
    })

    id: str
    project_id: str
    project_slug: str
    started_at: str
    task_raw: str
    terminal_phase: str | None
    total_elapsed_s: float | None
    garagem_outcome: str | None
    garagem_cost_usd: float | None
    meeseeks_outcome: str | None
    meeseeks_cost_usd: float | None
    merged_to_main: int | None
    assertiveness_score: int | None


class RunListResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items": [RunListItem.model_config["json_schema_extra"]["example"]],
            "total": 142,
            "limit": 50,
            "offset": 0,
        }
    })

    items: list[RunListItem]
    total: int
    limit: int
    offset: int


class RunDetail(BaseModel):
    """Detalhe completo. briefing_json e meeseeks_commits_json vêm já parseados."""
    model_config = ConfigDict(extra="allow")  # banco pode ganhar colunas no futuro

    id: str
    project_id: str
    project_slug: str
    started_at: str
    task_raw: str
    terminal_phase: str | None = None
    total_elapsed_s: float | None = None
    rerun_of: str | None = None

    garagem_model: str | None = None
    garagem_elapsed_s: float | None = None
    garagem_tokens_input: int | None = None
    garagem_tokens_output: int | None = None
    garagem_cost_usd: float | None = None
    garagem_turns: int | None = None
    garagem_outcome: str | None = None
    garagem_briefing_json: dict | list | None = None
    garagem_meeseeks_prompt: str | None = None
    garagem_criticality: str | None = None
    garagem_complexity: str | None = None
    garagem_commit_type: str | None = None
    garagem_slug: str | None = None

    meeseeks_model: str | None = None
    meeseeks_elapsed_s: float | None = None
    meeseeks_tokens_input: int | None = None
    meeseeks_tokens_output: int | None = None
    meeseeks_cost_usd: float | None = None
    meeseeks_outcome: str | None = None
    meeseeks_branch: str | None = None
    meeseeks_commits_json: list | None = None
    meeseeks_report: str | None = None
    meeseeks_confidence: float | None = None
    meeseeks_diff_added: int | None = None
    meeseeks_diff_deleted: int | None = None
    meeseeks_diff_files: int | None = None

    dev_server_outcome: str | None = None
    dev_server_port: int | None = None

    merged_to_main: int | None = None
    assertiveness_score: int | None = None
    review_note: str | None = None


class RunReviewPatch(BaseModel):
    """Body do PATCH /api/runs/{id}. Campos extras são ignorados (extra='ignore'
    — aceitar é mais gentil que recusar, vide brief)."""
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "merged_to_main": 1,
                "assertiveness_score": 4,
                "review_note": "ficou bom, só o estilo do commit que destoou",
            }
        },
    )

    merged_to_main: Literal[0, 1] | None = Field(
        default=None,
        description="1 = PR mergeado em main · 0 = descartado · null = sem decisão ainda.",
    )
    assertiveness_score: int | None = Field(
        default=None, ge=1, le=5,
        description="Nota 1–5 sobre quão alinhado o Meeseeks ficou com a intenção do Rick.",
    )
    review_note: str | None = Field(
        default=None,
        description="Comentário curto pro registro histórico.",
    )


# ─── projects ────────────────────────────────────────────────────────────


class ProjectItem(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "2a3d9f60-b2b1-4f0a-9c11-1d2e3f4a5b6c",
            "slug": "jogo",
            "name": "jogo",
            "path": "/home/eliezer/vnt/ASUS/jogo",
            "repo_url": None,
            "created_at": "2026-05-13T20:10:00+00:00",
        }
    })

    id: str
    slug: str
    name: str
    path: str
    repo_url: str | None
    created_at: str


class ProjectListResponse(BaseModel):
    items: list[ProjectItem]


# ─── metrics ─────────────────────────────────────────────────────────────


class DailyCost(BaseModel):
    dia: str
    usd: float


class DailyRuns(BaseModel):
    dia: str
    n: int


class OverviewResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "window_days": 30,
            "runs_total": 87,
            "custo_total_usd": 4.23,
            "tempo_medio_s": 92.1,
            "taxa_pushback": 0.18,
            "custo_por_dia": [
                {"dia": "2026-05-14", "usd": 0.45},
                {"dia": "2026-05-13", "usd": 0.32},
            ],
            "runs_por_dia": [
                {"dia": "2026-05-14", "n": 12},
                {"dia": "2026-05-13", "n": 7},
            ],
            "phase_breakdown": {
                "success": 60,
                "meeseeks_failure": 12,
                "garagem_pushback": 15,
            },
        }
    })

    window_days: int
    runs_total: int
    custo_total_usd: float
    tempo_medio_s: float | None
    taxa_pushback: float
    custo_por_dia: list[DailyCost]
    runs_por_dia: list[DailyRuns]
    phase_breakdown: dict[str, int]
