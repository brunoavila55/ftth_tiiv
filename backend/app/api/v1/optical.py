from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.core.contracts import pending_endpoint
from app.core.dependencies import require_permission, validate_csrf
from app.db.session import get_db
from app.modules.optical.service import (
    create_optical_profile,
    delete_optical_profile,
    get_optical_profile_by_id,
    list_optical_profiles_paginated,
    optical_profile_to_read,
    update_optical_profile,
)
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
    dependencies=[Depends(require_permission("optical:read"))],
)
def list_optical_profiles(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> PaginatedResponse[OpticalProfileRead]:
    items, total = list_optical_profiles_paginated(
        session=db,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse[OpticalProfileRead](
        items=[optical_profile_to_read(p) for p in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@optical_router.post(
    "/optical-profiles",
    response_model=OpticalProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar perfil óptico",
    dependencies=[Depends(require_permission("optical:write")), Depends(validate_csrf)],
)
def create_optical_profile_endpoint(
    payload: OpticalProfileCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> OpticalProfileRead:
    profile = create_optical_profile(session=db, payload=payload)
    response.headers["ETag"] = f'"{profile.version}"'
    return optical_profile_to_read(profile)


@optical_router.get(
    "/optical-profiles/{profile_id}",
    response_model=OpticalProfileRead,
    summary="Detalhes do perfil óptico",
    dependencies=[Depends(require_permission("optical:read"))],
)
def get_optical_profile_endpoint(
    profile_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> OpticalProfileRead:
    profile = get_optical_profile_by_id(session=db, profile_id=profile_id)
    response.headers["ETag"] = f'"{profile.version}"'
    return optical_profile_to_read(profile)


@optical_router.patch(
    "/optical-profiles/{profile_id}",
    response_model=OpticalProfileRead,
    summary="Atualizar perfil óptico",
    dependencies=[Depends(require_permission("optical:write")), Depends(validate_csrf)],
)
def update_optical_profile_endpoint(
    profile_id: str,
    payload: OpticalProfileUpdate,
    response: Response,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> OpticalProfileRead:
    profile = update_optical_profile(
        session=db, profile_id=profile_id, payload=payload, if_match=if_match
    )
    response.headers["ETag"] = f'"{profile.version}"'
    return optical_profile_to_read(profile)


@optical_router.delete(
    "/optical-profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar perfil óptico",
    dependencies=[Depends(require_permission("optical:write")), Depends(validate_csrf)],
)
def delete_optical_profile_endpoint(
    profile_id: str,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> None:
    delete_optical_profile(session=db, profile_id=profile_id, if_match=if_match)


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
def calculate_budget(payload: BudgetCalculationRequest) -> BudgetCalculationResponse:
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
def simulate_budget(payload: OpticalSimulationRequest) -> OpticalSimulationResponse:
    pending_endpoint("B12")
