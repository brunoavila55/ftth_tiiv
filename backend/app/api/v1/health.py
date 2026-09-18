from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.db.health import check_database_connectivity, check_database_migrations

health_router = APIRouter(tags=["Health"])


class LiveResponse(BaseModel):
    status: str = "alive"


class ReadyResponse(BaseModel):
    status: str
    database: dict[str, Any]
    migrations: dict[str, Any]


@health_router.get(
    "/live",
    response_model=LiveResponse,
    summary="Verificação de Liveness",
    description="Retorna 200 imediatamente se o processo HTTP estiver respondendo.",
)
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@health_router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Verificação de Readiness",
    description="Valida conectividade com o banco de dados e estado das migrações do Alembic sem expor credenciais.",
)
def readiness(response: Response) -> dict[str, Any]:
    # Conexão dedicada e curta (não usa o pool da aplicação): responde mesmo com a API saturada
    db_health = check_database_connectivity()
    if db_health.get("status") != "connected":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "database": db_health,
            "migrations": {"status": "skipped", "message": "Banco inacessível"},
        }

    migration_health = check_database_migrations()
    if migration_health.get("status") not in ("applied",):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "database": db_health,
            "migrations": migration_health,
        }

    return {
        "status": "ready",
        "database": db_health,
        "migrations": migration_health,
    }
