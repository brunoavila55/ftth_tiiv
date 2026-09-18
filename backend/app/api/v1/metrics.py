from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_optional_current_user
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.metrics import metrics_collector
from app.db.session import get_db, get_engine
from app.modules.identity.models import User

router = APIRouter(tags=["Observabilidade e Métricas"])


def verify_metrics_access(
    request: Request,
    x_metrics_token: str | None = Header(None, alias="X-Metrics-Token"),
    current_user: User | None = Depends(get_optional_current_user),
) -> None:
    """Valida acesso restrito às métricas (B16).

    Requer:
    - Cabeçalho 'X-Metrics-Token' coincidente com METRICS_SECRET_TOKEN configurado, OU
    - Usuário autenticado com perfil 'admin'.
    """
    settings = get_settings()

    # 1. Validação por token de monitoramento (Prometheus / agentes de observabilidade)
    if x_metrics_token and x_metrics_token == settings.METRICS_SECRET_TOKEN:
        return

    # 2. Validação por usuário autenticado com perfil de administrador
    if current_user:
        if current_user.role == "admin":
            return
        raise ForbiddenError(
            "Acesso restrito: apenas operadores administradores podem consultar métricas.",
            code="metrics_forbidden",
        )

    raise UnauthorizedError(
        "Acesso restrito às métricas. Forneça o cabeçalho X-Metrics-Token ou sessão de administrador.",
        code="metrics_unauthorized",
    )


@router.get(
    "/metrics",
    summary="Obter métricas de latência, erros, banco de dados e observabilidade",
    description="Retorna métricas operacionais no formato Prometheus (padrão) ou JSON estruturado (?format=json). Acesso restrito a administradores ou agentes com token.",
    dependencies=[Depends(verify_metrics_access)],
)
def get_metrics(
    request: Request,
    format: str | None = Query(
        None, description="Formato de saída: 'json' ou 'prometheus' (padrão)"
    ),
    db: Session = Depends(get_db),
) -> Any:
    """Endpoint restrito de métricas operacionais e de desempenho."""
    engine = get_engine()
    accept_header = request.headers.get("accept", "")

    # Se solicitado explicitamente JSON via query param ou Accept header
    if format == "json" or "application/json" in accept_header:
        return metrics_collector.get_json_metrics(engine=engine, db=db)

    # Formato padrão Prometheus texto puro
    prometheus_data = metrics_collector.to_prometheus_text(engine=engine, db=db)
    return Response(
        content=prometheus_data,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
