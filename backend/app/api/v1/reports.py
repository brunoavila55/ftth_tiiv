
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission
from app.db.session import get_db
from app.modules.cables.models import Cable
from app.modules.gis.service import get_topology_revision
from app.modules.inventory.models import Site, Structure
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.reports import (
    AuditEventRead,
    CTOOccupancyBuckets,
    DashboardSummaryResponse,
    GlobalSearchResponse,
    SearchGroup,
    SearchResultItem,
)

reports_router = APIRouter(tags=["Relatórios, Busca e Auditoria"])


@reports_router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="Resumo de indicadores do painel",
    description="Retorna contadores de ativos, faixas de ocupação de CTOs e alertas de incompletude técnica.",
)
def get_dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummaryResponse:
    total_sites = db.query(Site).filter(Site.status != "retired").count()
    total_structures = db.query(Structure).filter(Structure.status != "retired").count()
    total_cables = db.query(Cable).filter(Cable.status != "retired").count()

    alerts: list[str] = []
    cables_without_segments = (
        db.query(Cable).filter(Cable.status != "retired", ~Cable.segments.any()).count()
    )
    if cables_without_segments > 0:
        alerts.append(
            f"{cables_without_segments} cabo(s) cadastrado(s) sem nenhum segmento georreferenciado"
        )

    ctos_count = (
        db.query(Structure)
        .filter(Structure.status != "retired", Structure.kind == "cto")
        .count()
    )

    ctos_occupancy = CTOOccupancyBuckets(
        empty_0_pct=ctos_count,
        low_1_to_50_pct=0,
        high_51_to_99_pct=0,
        full_100_pct=0,
    )

    current_rev = get_topology_revision(db)

    return DashboardSummaryResponse(
        total_sites=total_sites,
        total_structures=total_structures,
        total_cables=total_cables,
        total_customers=0,
        total_active_service_links=0,
        ctos_occupancy=ctos_occupancy,
        incomplete_documentation_alerts=alerts,
        topology_revision=current_rev,
    )


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
    db: Session = Depends(get_db),
) -> GlobalSearchResponse:
    clean_q = q.strip()
    groups: list[SearchGroup] = []
    total_results = 0

    # Sites
    site_matches = (
        db.query(Site)
        .filter(
            Site.status != "retired",
            or_(Site.code.ilike(f"%{clean_q}%"), Site.name.ilike(f"%{clean_q}%")),
        )
        .limit(limit)
        .all()
    )
    if site_matches:
        site_items = [
            SearchResultItem(
                id=str(s.id),
                entity_type="site",
                code=s.code,
                name=s.name,
                status=s.status,
            )
            for s in site_matches
        ]
        groups.append(SearchGroup(entity_type="site", items=site_items))
        total_results += len(site_items)

    # Structures
    structure_matches = (
        db.query(Structure)
        .filter(
            Structure.status != "retired",
            Structure.code.ilike(f"%{clean_q}%"),
        )
        .limit(limit)
        .all()
    )
    if structure_matches:
        structure_items = [
            SearchResultItem(
                id=str(st.id),
                entity_type=st.kind,
                code=st.code,
                name=None,
                status=st.status,
            )
            for st in structure_matches
        ]
        groups.append(SearchGroup(entity_type="structure", items=structure_items))
        total_results += len(structure_items)

    # Cables
    cable_matches = (
        db.query(Cable)
        .filter(
            Cable.status != "retired",
            or_(Cable.code.ilike(f"%{clean_q}%"), Cable.model.ilike(f"%{clean_q}%")),
        )
        .limit(limit)
        .all()
    )
    if cable_matches:
        cable_items = [
            SearchResultItem(
                id=str(c.id),
                entity_type="cable",
                code=c.code,
                name=c.model,
                status=c.status,
            )
            for c in cable_matches
        ]
        groups.append(SearchGroup(entity_type="cable", items=cable_items))
        total_results += len(cable_items)

    return GlobalSearchResponse(
        query=clean_q,
        total_results=total_results,
        groups=groups,
    )


@reports_router.get(
    "/audit-events",
    response_model=PaginatedResponse[AuditEventRead],
    summary="Consultar trilha de auditoria append-only",
    description="Retorna histórico ordenado de mutações e ações de usuários no sistema.",
    dependencies=[Depends(require_permission("audit:read"))],
)
def list_audit_events(
    pagination: PaginationParams = Depends(),
    entity_type: str | None = Query(default=None, description="Filtrar por tipo de entidade"),
    entity_id: str | None = Query(default=None, description="Filtrar por UUID da entidade"),
    actor_id: str | None = Query(default=None, description="Filtrar por UUID do autor"),
    action: str | None = Query(default=None, description="Filtrar por tipo de ação"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AuditEventRead]:
    import uuid

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

    results = [
        AuditEventRead(
            id=str(e.id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            actor_name=e.actor_name,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=str(e.entity_id),
            changes=e.changes or {},
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
