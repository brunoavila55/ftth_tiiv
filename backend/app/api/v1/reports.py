from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.contracts import pending_endpoint
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.reports import (
    AuditEventRead,
    DashboardSummaryResponse,
    GlobalSearchResponse,
)

reports_router = APIRouter(tags=["Relatórios, Busca e Auditoria"])


@reports_router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="Resumo de indicadores do painel",
    description="Retorna contadores de ativos, faixas de ocupação de CTOs e alertas de incompletude técnica.",
)
def get_dashboard_summary() -> Any:
    pending_endpoint("B15")


@reports_router.get(
    "/search",
    response_model=GlobalSearchResponse,
    summary="Busca global no inventário e rede",
    description="Realiza busca textual indexada por código, nome ou serial com agrupamento por tipo de entidade.",
)
def global_search(
    q: str = Query(..., min_length=2, description="Termo de pesquisa"),
    limit: int = Query(
        default=20, ge=1, le=100, description="Limite máximo de resultados por grupo"
    ),
) -> Any:
    pending_endpoint("B15")


@reports_router.get(
    "/audit-events",
    response_model=PaginatedResponse[AuditEventRead],
    summary="Consultar trilha de auditoria append-only",
    description="Retorna histórico ordenado de mutações e ações de usuários no sistema.",
)
def list_audit_events(
    pagination: PaginationParams = Depends(),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
) -> Any:
    pending_endpoint("B13")
