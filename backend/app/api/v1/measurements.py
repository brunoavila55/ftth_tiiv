
from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.db.session import get_db
from app.modules.identity.models import User
from app.modules.measurements.service import (
    compare_measurement,
    create_measurement,
    delete_measurement,
    get_measurement_by_id,
    list_measurements_paginated,
    measurement_to_read,
    update_measurement,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.measurements import (
    MeasurementComparisonResponse,
    MeasurementCreate,
    MeasurementRead,
    MeasurementUpdate,
)

measurements_router = APIRouter(prefix="/measurements", tags=["Medições de Potência"])


@measurements_router.get(
    "",
    response_model=PaginatedResponse[MeasurementRead],
    summary="Listar medições de potência",
    dependencies=[Depends(require_permission("measurements:read"))],
)
def list_measurements_endpoint(
    pagination: PaginationParams = Depends(),
    service_link_id: str | None = Query(default=None, description="Filtrar por atendimento de cliente"),
    terminal_id: str | None = Query(default=None, description="Filtrar por terminal óptico"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[MeasurementRead]:
    items, total = list_measurements_paginated(
        session=db,
        page=pagination.page,
        page_size=pagination.page_size,
        service_link_id=service_link_id,
        terminal_id=terminal_id,
    )
    return PaginatedResponse[MeasurementRead](
        items=[measurement_to_read(m) for m in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@measurements_router.post(
    "",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar medição manual",
    dependencies=[Depends(require_permission("measurements:write")), Depends(validate_csrf)],
)
def create_measurement_endpoint(
    payload: MeasurementCreate,
    response: Response,
    current_user: User = Depends(require_permission("measurements:write")),
    db: Session = Depends(get_db),
) -> MeasurementRead:
    measurement = create_measurement(session=db, payload=payload, user_id=str(current_user.id))
    response.headers["ETag"] = f'"{measurement.version}"'
    return measurement_to_read(measurement)


@measurements_router.get(
    "/{measurement_id}",
    response_model=MeasurementRead,
    summary="Detalhes da medição",
    dependencies=[Depends(require_permission("measurements:read"))],
)
def get_measurement_endpoint(
    measurement_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> MeasurementRead:
    measurement = get_measurement_by_id(session=db, measurement_id=measurement_id)
    response.headers["ETag"] = f'"{measurement.version}"'
    return measurement_to_read(measurement)


@measurements_router.patch(
    "/{measurement_id}",
    response_model=MeasurementRead,
    summary="Atualizar notas da medição",
    dependencies=[Depends(require_permission("measurements:write")), Depends(validate_csrf)],
)
def update_measurement_endpoint(
    measurement_id: str,
    payload: MeasurementUpdate,
    response: Response,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    db: Session = Depends(get_db),
) -> MeasurementRead:
    measurement = update_measurement(
        session=db, measurement_id=measurement_id, payload=payload, if_match=if_match
    )
    response.headers["ETag"] = f'"{measurement.version}"'
    return measurement_to_read(measurement)


@measurements_router.delete(
    "/{measurement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir medição",
    dependencies=[Depends(require_permission("measurements:write")), Depends(validate_csrf)],
)
def delete_measurement_endpoint(
    measurement_id: str,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    db: Session = Depends(get_db),
) -> None:
    delete_measurement(session=db, measurement_id=measurement_id, if_match=if_match)


@measurements_router.get(
    "/{measurement_id}/compare",
    response_model=MeasurementComparisonResponse,
    summary="Comparar medição de campo com potência prevista",
    description="Calcula a perda excedente em dB comparando o valor medido com o orçamento óptico da revisão correspondente.",
    dependencies=[Depends(require_permission("measurements:read"))],
)
def compare_measurement_endpoint(
    measurement_id: str,
    tolerance_db: float = Query(default=2.0, ge=0.0, description="Tolerância de atenuação excessiva aceitável em dB"),
    db: Session = Depends(get_db),
) -> MeasurementComparisonResponse:
    return compare_measurement(session=db, measurement_id=measurement_id, tolerance_db=tolerance_db)
