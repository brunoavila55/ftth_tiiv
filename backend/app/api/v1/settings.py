from typing import Any

from fastapi import APIRouter, Header

from app.core.contracts import pending_endpoint
from app.schemas.settings import AppSettingsRead, AppSettingsUpdate

settings_router = APIRouter(prefix="/settings", tags=["Configurações da Organização"])


@settings_router.get(
    "",
    response_model=AppSettingsRead,
    summary="Consultar configurações da aplicação",
    description="Retorna preferências operacionais, fuso horário, limites e configurações geográficas.",
)
def get_app_settings() -> Any:
    pending_endpoint("B03")


@settings_router.patch(
    "",
    response_model=AppSettingsRead,
    summary="Atualizar configurações da aplicação",
    description="Atualiza parâmetros gerais da organização. Exige cabeçalho If-Match.",
)
def update_app_settings(
    payload: AppSettingsUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B03")
