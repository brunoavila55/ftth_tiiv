from typing import Any

from fastapi import APIRouter, status

from app.core.contracts import pending_endpoint
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
)
def trace_path(payload: TraceRequest) -> Any:
    pending_endpoint("B09")


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
