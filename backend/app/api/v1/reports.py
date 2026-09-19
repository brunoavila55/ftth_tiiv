import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.privacy import mask_pii_changes, user_can
from app.core.rate_limit import rate_limit
from app.core.search import MIN_SEARCH_LENGTH
from app.db.session import get_db
from app.modules.identity.models import User
from app.modules.reports.service import (
    calculate_dashboard_summary,
    execute_global_search,
    get_cable_capacity_report,
    get_cto_occupancy_report,
    get_inconsistencies_report,
)
from app.schemas.common import PaginatedResponse, PaginationParams, UuidStr
from app.schemas.reports import (
    AuditEventRead,
    CableCapacityReportItem,
    CTOOccupancyReportItem,
    DashboardSummaryResponse,
    GlobalSearchResponse,
    InconsistencyReportItem,
)

reports_router = APIRouter(tags=["Relatórios, Busca e Auditoria"])


@reports_router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="Resumo de indicadores do painel",
    description="Retorna contadores de ativos, faixas de ocupação de CTOs e alertas de incompletude técnica.",
    dependencies=[Depends(require_permission("reports:read"))],
)
def get_dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummaryResponse:
    return calculate_dashboard_summary(db)


@reports_router.get(
    "/search",
    response_model=GlobalSearchResponse,
    summary="Busca global no inventário e rede",
    description="Realiza busca textual indexada por código, nome ou serial com agrupamento por tipo de entidade e escopo autorizado.",
    dependencies=[Depends(rate_limit("search", "RATE_LIMIT_SEARCH_PER_MINUTE"))],
)
def global_search(
    q: str = Query(
        ...,
        min_length=MIN_SEARCH_LENGTH,
        max_length=100,
        description="Termo de pesquisa (mínimo de 3 caracteres: os índices trigram só atendem a partir daí)",
    ),
    limit: int = Query(
        default=20, ge=1, le=100, description="Limite máximo de resultados por grupo"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GlobalSearchResponse:
    return execute_global_search(db=db, q=q, limit=limit, current_user=current_user)


@reports_router.get(
    "/reports/ctos",
    response_model=PaginatedResponse[CTOOccupancyReportItem],
    summary="Relatório de capacidade e ocupação de CTOs",
    description="Lista caixas CTO com contagem exata de portas totais, ocupadas, reservadas, livres e taxa de ocupação.",
    dependencies=[Depends(require_permission("reports:read"))],
)
def list_cto_occupancy_report(
    pagination: PaginationParams = Depends(),
    site_id: UuidStr | None = Query(default=None, description="Filtrar por UUID do Site"),
    min_occupancy_pct: float | None = Query(
        default=None, ge=0, le=100, description="Ocupação mínima %"
    ),
    max_occupancy_pct: float | None = Query(
        default=None, ge=0, le=100, description="Ocupação máxima %"
    ),
    status: str | None = Query(default=None, description="Filtrar por status da estrutura"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CTOOccupancyReportItem]:
    s_uuid: uuid.UUID | None = None
    if site_id:
        try:
            s_uuid = uuid.UUID(site_id)
        except ValueError as err:
            raise HTTPException(status_code=422, detail=f"site_id inválido: '{site_id}'") from err

    items, total = get_cto_occupancy_report(
        db=db,
        site_id=s_uuid,
        min_occupancy_pct=min_occupancy_pct,
        max_occupancy_pct=max_occupancy_pct,
        status_filter=status,
        limit=pagination.page_size,
        offset=(pagination.page - 1) * pagination.page_size,
    )

    return PaginatedResponse[CTOOccupancyReportItem](
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@reports_router.get(
    "/reports/cables",
    response_model=PaginatedResponse[CableCapacityReportItem],
    summary="Relatório de capacidade óptica de cabos",
    description="Lista cabos com total de fibras, fibras conectadas, reservadas, livres, danificadas e taxa de utilização.",
    dependencies=[Depends(require_permission("reports:read"))],
)
def list_cable_capacity_report(
    pagination: PaginationParams = Depends(),
    status: str | None = Query(default=None, description="Filtrar por status do cabo"),
    min_usage_pct: float | None = Query(
        default=None, ge=0, le=100, description="Utilização mínima %"
    ),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CableCapacityReportItem]:
    items, total = get_cable_capacity_report(
        db=db,
        status_filter=status,
        min_usage_pct=min_usage_pct,
        limit=pagination.page_size,
        offset=(pagination.page - 1) * pagination.page_size,
    )

    return PaginatedResponse[CableCapacityReportItem](
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@reports_router.get(
    "/reports/inconsistencies",
    response_model=PaginatedResponse[InconsistencyReportItem],
    summary="Relatório de inconsistências e pendências da rede",
    description="Lista anomalias técnicas, cadastros incompletos e problemas de integridade física e óptica.",
    dependencies=[Depends(require_permission("reports:read"))],
)
def list_inconsistencies_report(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> PaginatedResponse[InconsistencyReportItem]:
    items, total = get_inconsistencies_report(
        db=db,
        limit=pagination.page_size,
        offset=(pagination.page - 1) * pagination.page_size,
    )

    return PaginatedResponse[InconsistencyReportItem](
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@reports_router.get(
    "/audit-events",
    response_model=PaginatedResponse[AuditEventRead],
    summary="Consultar trilha de auditoria append-only",
    description=(
        "Trilha append-only (imutável no banco) de TODAS as mutações da API — cadastros, cabos e "
        "segmentos, conexões, medições, anexos, importações/exportações, usuários — e de "
        "autenticação (login, falha de login, logout, troca de senha). Cada evento traz ator, "
        "request_id e o diff da alteração (nunca segredos). Campos pessoais de clientes "
        "(phone, email, address) são mascarados para quem não tem customers:read."
    ),
)
def list_audit_events(
    pagination: PaginationParams = Depends(),
    entity_type: str | None = Query(default=None, description="Filtrar por tipo de entidade"),
    entity_id: UuidStr | None = Query(default=None, description="Filtrar por UUID da entidade"),
    actor_id: UuidStr | None = Query(default=None, description="Filtrar por UUID do autor"),
    action: str | None = Query(default=None, description="Filtrar por tipo de ação"),
    current_user: User = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AuditEventRead]:
    e_uuid: uuid.UUID | None = None
    if entity_id:
        try:
            e_uuid = uuid.UUID(entity_id)
        except ValueError as err:
            raise HTTPException(
                status_code=422,
                detail=f"entity_id inválido: '{entity_id}'",
            ) from err

    a_uuid: uuid.UUID | None = None
    if actor_id:
        try:
            a_uuid = uuid.UUID(actor_id)
        except ValueError as err:
            raise HTTPException(
                status_code=422,
                detail=f"actor_id inválido: '{actor_id}'",
            ) from err

    from app.modules.audit.service import list_audit_events_paginated

    events, total = list_audit_events_paginated(
        db,
        entity_type=entity_type,
        entity_id=e_uuid,
        actor_id=a_uuid,
        action=action,
        limit=pagination.page_size,
        offset=(pagination.page - 1) * pagination.page_size,
    )

    can_see_pii = user_can(current_user, "customers:read")
    results = [
        AuditEventRead(
            id=str(e.id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            actor_name=e.actor_name,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=str(e.entity_id),
            changes=(e.changes or {}) if can_see_pii else mask_pii_changes(e.changes or {}),
            reason=e.reason,
            request_id=e.request_id,
            created_at=e.created_at,
        )
        for e in events
    ]

    return PaginatedResponse[AuditEventRead](
        items=results,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
