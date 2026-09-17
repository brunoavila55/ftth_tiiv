from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.contracts import pending_endpoint
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.measurements import (
    MeasurementComparisonResponse,
    MeasurementCreate,
    MeasurementRead,
    MeasurementUpdate,
)

measurements_router = APIRouter(prefix="/measurements", tags=["Medições de Potência"])


@measurements_router.get(
    "", response_model=PaginatedResponse[MeasurementRead], summary="Listar medições de potência"
)
def list_measurements(
    pagination: PaginationParams = Depends(),
    service_link_id: str | None = Query(default=None),
    terminal_id: str | None = Query(default=None),
) -> Any:
    pending_endpoint("B11")


@measurements_router.post(
    "",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar medição manual",
)
def create_measurement(payload: MeasurementCreate) -> Any:
    pending_endpoint("B11")


@measurements_router.get(
    "/{measurement_id}", response_model=MeasurementRead, summary="Detalhes da medição"
)
def get_measurement(measurement_id: str) -> Any:
    pending_endpoint("B11")


@measurements_router.patch(
    "/{measurement_id}", response_model=MeasurementRead, summary="Atualizar notas da medição"
)
def update_measurement(
    measurement_id: str,
    payload: MeasurementUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B11")


@measurements_router.delete(
    "/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir medição"
)
def delete_measurement(
    measurement_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B11")


@measurements_router.get(
    "/{measurement_id}/compare",
    response_model=MeasurementComparisonResponse,
    summary="Comparar medição de campo com potência prevista",
    description="Calcula a perda excedente em dB comparando o valor medido com o orçamento óptico da revisão correspondente.",
)
def compare_measurement(measurement_id: str) -> Any:
    pending_endpoint("B11")
