from typing import Any

from fastapi import APIRouter, Depends, Header, status

from app.core.contracts import pending_endpoint
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.optical import (
    BudgetCalculationRequest,
    BudgetCalculationResponse,
    OpticalProfileCreate,
    OpticalProfileRead,
    OpticalProfileUpdate,
    OpticalSimulationRequest,
    OpticalSimulationResponse,
)

optical_router = APIRouter(tags=["Cálculo Óptico e Perfis"])


# ==============================================================================
# OPTICAL PROFILES (Perfis de Transmissão / Tecnologias)
# ==============================================================================
@optical_router.get(
    "/optical-profiles",
    response_model=PaginatedResponse[OpticalProfileRead],
    summary="Listar perfis ópticos",
)
def list_optical_profiles(pagination: PaginationParams = Depends()) -> Any:
    pending_endpoint("B04")


@optical_router.post(
    "/optical-profiles",
    response_model=OpticalProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar perfil óptico",
)
def create_optical_profile(payload: OpticalProfileCreate) -> Any:
    pending_endpoint("B04")


@optical_router.get(
    "/optical-profiles/{profile_id}",
    response_model=OpticalProfileRead,
    summary="Detalhes do perfil óptico",
)
def get_optical_profile(profile_id: str) -> Any:
    pending_endpoint("B04")


@optical_router.patch(
    "/optical-profiles/{profile_id}",
    response_model=OpticalProfileRead,
    summary="Atualizar perfil óptico",
)
def update_optical_profile(
    profile_id: str,
    payload: OpticalProfileUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B04")


@optical_router.delete(
    "/optical-profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar perfil óptico",
)
def delete_optical_profile(
    profile_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B04")


# ==============================================================================
# OPTICAL CALCULATIONS (Orçamento e Simulação de Potência)
# ==============================================================================
@optical_router.post(
    "/optical/budgets",
    response_model=BudgetCalculationResponse,
    status_code=status.HTTP_200_OK,
    summary="Calcular orçamento de potência óptica (Link Budget)",
    description=(
        "Calcula atenuação acumulada, potência RX prevista, margem de engenharia "
        "e sobrecarga para um atendimento documentado."
    ),
)
def calculate_budget(payload: BudgetCalculationRequest) -> Any:
    pending_endpoint("B10")


@optical_router.post(
    "/optical/simulations",
    response_model=OpticalSimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulação óptica com parâmetros hipotéticos",
    description=(
        "Compara o orçamento de potência original com um cenário hipotético que aplica overrides "
        "em perdas, comprimentos ou splitters."
    ),
)
def simulate_budget(payload: OpticalSimulationRequest) -> Any:
    pending_endpoint("B12")
