"""Endpoint de métricas agregadas — alimenta o dashboard de governança."""

from fastapi import APIRouter, Depends, Query

from api.deps import get_logger
from api.models import OverviewResponse
from logger import RunLogger

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Agregados pro dashboard de governança",
    description=(
        "Janela retroativa de **N dias** sobre `started_at`. Inclui totais, "
        "custo somado (garagem + meeseeks), tempo médio, taxa de pushback "
        "(runs cuja `terminal_phase` começa com `garagem_*`), séries diárias "
        "e `phase_breakdown` agrupado.\n\n"
        "Dias sem runs **não aparecem** nas séries — frontend decide se "
        "plota como zero ou pula."
    ),
    responses={
        422: {"description": "days fora do intervalo [1, 365]."},
    },
)
def overview(
    days: int = Query(default=30, ge=1, le=365, description="Janela retroativa em dias."),
    logger: RunLogger = Depends(get_logger),
) -> OverviewResponse:
    return OverviewResponse.model_validate(logger.overview_metrics(days=days))
