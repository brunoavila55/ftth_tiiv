from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.db.session import get_db
from app.modules.app_settings import service
from app.schemas.settings import AppSettingsRead, AppSettingsUpdate

settings_router = APIRouter(prefix="/settings", tags=["Configurações da Organização"])


@settings_router.get(
    "",
    response_model=AppSettingsRead,
    summary="Consultar configurações da aplicação",
    description="Retorna preferências operacionais, fuso horário, limites e configurações geográficas.",
    dependencies=[Depends(require_permission("settings:read"))],
)
def get_app_settings(response: Response, db: Session = Depends(get_db)) -> AppSettingsRead:
    result = service.get_app_settings(db)
    response.headers["ETag"] = f'"{result.version}"'
    return result


@settings_router.patch(
    "",
    response_model=AppSettingsRead,
    summary="Atualizar configurações da aplicação",
    description="Atualiza parâmetros gerais da organização. Exige cabeçalho If-Match.",
    dependencies=[Depends(require_permission("settings:write")), Depends(validate_csrf)],
)
def update_app_settings(
    payload: AppSettingsUpdate,
    response: Response,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    db: Session = Depends(get_db),
) -> AppSettingsRead:
    result = service.update_app_settings(db, payload=payload, if_match=if_match)
    response.headers["ETag"] = f'"{result.version}"'
    return result
