from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.contracts import pending_endpoint
from app.core.dependencies import require_permission
from app.db.session import get_db
from app.modules.topology import service
from app.schemas.topology import (
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    TraceRequest,
    TraceResponse,
)

topology_router = APIRouter(prefix="/topology", tags=["Topologia e Grafo Óptico"])


@topology_router.post(
    "/trace",
    response_model=TraceResponse,
    status_code=status.HTTP_200_OK,
    summary="Rastreamento óptico ponta a ponta",
    description=(
        "Executa travessia consistente no grafo óptico a partir de um terminal de origem (PON ou ONU) "
        "com validação semântica de splitters e travessias internas."
    ),
    dependencies=[Depends(require_permission("network:read"))],
)
def trace_path(
    payload: TraceRequest,
    db: Session = Depends(get_db),
) -> Any:
    return service.trace_optical_path(db, payload)


@topology_router.post(
    "/impact",
    response_model=ImpactAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Análise de impacto de rompimento de cabos",
    description=(
        "Simula a remoção virtual de trechos de cabos em um snapshot consistente da rede "
        "sem alterar dados operacionais, retornando os clientes e CTOs afetados."
    ),
)
def analyze_impact(payload: ImpactAnalysisRequest) -> Any:
    pending_endpoint("B12")
