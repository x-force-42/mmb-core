"""Endpoints de runs — lista, detalhe e PATCH de review manual."""

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_logger
from api.models import (
    RunDetail,
    RunListItem,
    RunListResponse,
    RunReviewPatch,
)
from logger import RunLogger

router = APIRouter(prefix="/api/runs", tags=["runs"])


OrderBy = Literal[
    "started_at:desc",
    "started_at:asc",
    "total_elapsed_s:desc",
    "total_elapsed_s:asc",
]

Phase = Literal[
    "success",
    "meeseeks_failure",
    "dev_server_failure",
    "garagem_pushback",
    "garagem_no_slug",
    "garagem_error",
]


@router.get(
    "",
    response_model=RunListResponse,
    summary="Lista runs paginada",
    description=(
        "Histórico de execuções do `/meeseeks` com filtros opcionais.\n\n"
        "- **project**: slug do projeto-alvo.\n"
        "- **phase**: terminal_phase exato (use os valores do enum).\n"
        "- **from / to**: janela ISO sobre `started_at` (`YYYY-MM-DD`).\n"
        "- **limit / offset**: paginação (limit cap em 200).\n"
        "- **order**: ordenação — `started_at` ou `total_elapsed_s`, asc/desc."
    ),
    responses={
        422: {"description": "Parâmetro fora do domínio (phase/order inválido, limit > 200, etc)."},
    },
)
def list_runs(
    project: str | None = Query(default=None, description="Slug do projeto.", examples=["jogo"]),
    phase: Phase | None = Query(default=None, description="Filtra por terminal_phase exato."),
    from_: str | None = Query(default=None, alias="from", description="Janela inicial (ISO).", examples=["2026-05-01"]),
    to: str | None = Query(default=None, description="Janela final (ISO).", examples=["2026-05-14"]),
    limit: int = Query(default=50, ge=1, le=200, description="Tamanho da página (max 200)."),
    offset: int = Query(default=0, ge=0, description="Offset pra paginar."),
    order: OrderBy = Query(default="started_at:desc", description="Ordenação."),
    logger: RunLogger = Depends(get_logger),
) -> RunListResponse:
    items, total = logger.list_runs(
        project_slug=project,
        phase=phase,
        from_iso=from_,
        to_iso=to,
        limit=limit,
        offset=offset,
        order=order,
    )
    return RunListResponse(
        items=[RunListItem.model_validate(it) for it in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{run_id}",
    response_model=RunDetail,
    summary="Detalhe completo de uma run",
    description=(
        "Devolve todos os campos da tabela `runs` + `project_slug` joinado. "
        "Os campos `garagem_briefing_json` e `meeseeks_commits_json` saem "
        "**já parseados** como objeto/array, não como string."
    ),
    responses={
        404: {
            "description": "Run não encontrado.",
            "content": {"application/json": {"example": {"detail": "run não encontrado"}}},
        },
    },
)
def get_run(run_id: str, logger: RunLogger = Depends(get_logger)) -> RunDetail:
    row = logger.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run não encontrado")
    project = logger.get_project(row["project_id"])
    row["project_slug"] = project["slug"] if project else None
    row["garagem_briefing_json"] = _parse_json(row.get("garagem_briefing_json"))
    row["meeseeks_commits_json"] = _parse_json(row.get("meeseeks_commits_json"))
    return RunDetail.model_validate(row)


@router.patch(
    "/{run_id}",
    response_model=RunDetail,
    summary="Atualiza review manual de uma run",
    description=(
        "Persiste **apenas** os 3 campos manuais de review:\n\n"
        "- `merged_to_main` — `0`, `1` ou `null`.\n"
        "- `assertiveness_score` — `1`–`5` ou `null`.\n"
        "- `review_note` — texto livre ou `null`.\n\n"
        "Qualquer outro campo no body é **silenciosamente ignorado** "
        "(não retorna erro). Devolve o run completo atualizado."
    ),
    responses={
        404: {"description": "Run não encontrado."},
        422: {"description": "Valor fora do domínio (ex: assertiveness=6)."},
    },
)
def patch_run(
    run_id: str,
    body: RunReviewPatch,
    logger: RunLogger = Depends(get_logger),
) -> RunDetail:
    ok = logger.update_run_review(
        run_id,
        merged_to_main=body.merged_to_main,
        assertiveness_score=body.assertiveness_score,
        review_note=body.review_note,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="run não encontrado")
    return get_run(run_id, logger=logger)


def _parse_json(value):
    """Decodifica JSON armazenado como string. Devolve None se inválido —
    não derruba a resposta inteira por causa de uma linha corrompida."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError) as e:
        print(f"[warn] json inválido no banco: {e}")
        return None
