"""Endpoint de projetos — lista simples."""

from fastapi import APIRouter, Depends

from api.deps import get_logger
from api.models import ProjectItem, ProjectListResponse
from logger import RunLogger

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="Lista todos os projetos cadastrados",
    description=(
        "Sem paginação — volume esperado é dezenas, não milhares. "
        "Ordenado por `slug`."
    ),
)
def list_projects(logger: RunLogger = Depends(get_logger)) -> ProjectListResponse:
    items = logger.list_projects()
    return ProjectListResponse(
        items=[ProjectItem.model_validate(it) for it in items],
    )
