from enum import StrEnum

from pydantic import BaseModel, Field


class TraceDirection(StrEnum):
    DOWNSTREAM = "downstream"
    UPSTREAM = "upstream"


class TraceStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    AMBIGUOUS = "ambiguous"
    CYCLE_DETECTED = "cycle_detected"
    LIMIT_EXCEEDED = "limit_exceeded"


class TraceRequest(BaseModel):
    start_terminal_id: str = Field(..., description="UUID do terminal de início da travessia")
    direction: TraceDirection = Field(
        default=TraceDirection.DOWNSTREAM,
        description="Direção da propagação do sinal óptico: downstream (PON->ONU) ou upstream (ONU->PON)",
    )
    max_results: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Limite máximo de caminhos ou derivações retornados",
    )
    max_hops: int = Field(
        default=200,
        ge=1,
        le=500,
        description="Limite máximo de saltos ou elementos ópticos por caminho antes de truncar",
    )


class TraceStep(BaseModel):
    step_number: int = Field(
        ..., ge=1, description="Ordem sequencial do elemento no caminho óptico"
    )
    element_type: str = Field(
        ...,
        description="Tipo do elemento (fiber_segment, fusion, patch_cord, splitter, port_pass_through)",
    )
    element_id: str = Field(..., description="UUID do recurso atravessado")
    element_code: str | None = Field(
        default=None, description="Código de identificação do elemento"
    )
    input_terminal_id: str | None = Field(default=None, description="Terminal óptico de entrada")
    output_terminal_id: str | None = Field(default=None, description="Terminal óptico de saída")
    length_m: float = Field(
        default=0.0, ge=0.0, description="Comprimento óptico do passo em metros"
    )
    loss_db: float = Field(
        default=0.0, ge=0.0, description="Perda óptica individual do passo em dB"
    )
    accumulated_length_m: float = Field(
        default=0.0, ge=0.0, description="Comprimento óptico acumulado até o passo em metros"
    )
    accumulated_loss_db: float = Field(
        default=0.0, ge=0.0, description="Perda óptica acumulada até o passo em dB"
    )
    location_code: str | None = Field(
        default=None, description="Código da estrutura física onde o passo ocorre"
    )


class TracePath(BaseModel):
    path_id: str = Field(
        ..., description="Identificador único determinístico do caminho nesta revisão"
    )
    origin_terminal_id: str = Field(..., description="Terminal inicial do caminho")
    destination_terminal_id: str | None = Field(
        default=None, description="Terminal final alcançado (ex: porta óptica da ONU)"
    )
    total_length_m: float = Field(
        ..., ge=0.0, description="Comprimento óptico total do caminho em metros"
    )
    total_loss_db: float = Field(..., ge=0.0, description="Perda óptica total do caminho em dB")
    steps: list[TraceStep] = Field(..., description="Lista sequencial e ordenada de passos ópticos")


class TraceResponse(BaseModel):
    topology_revision: int = Field(..., description="Revisão da topologia usada no rastreamento")
    status: TraceStatus = Field(..., description="Status de conclusão do rastreamento")
    paths: list[TracePath] = Field(..., description="Caminhos ópticos válidos encontrados")
    warnings: list[str] = Field(
        default_factory=list, description="Avisos e inconsistências detectadas"
    )
    unresolved_terminals: list[str] = Field(
        default_factory=list, description="Terminais com ponta aberta ou sem continuidade"
    )


class ImpactAnalysisRequest(BaseModel):
    cable_segment_ids: list[str] = Field(
        ...,
        min_length=1,
        description="Lista de UUIDs dos trechos de cabo rompidos ou sob teste",
        max_length=500,
    )
    expected_topology_revision: int = Field(
        ..., description="Revisão topológica esperada do cenário de rede", le=2147483647
    )


class ImpactedCustomerItem(BaseModel):
    customer_id: str
    customer_code: str
    service_link_id: str
    onu_device_code: str
    cto_code: str


class ImpactAnalysisResponse(BaseModel):
    topology_revision: int
    broken_segments_count: int
    impacted_customers: list[ImpactedCustomerItem] = Field(
        ..., description="Clientes ativos que perderam o enlace óptico"
    )
    unaffected_customers_count: int = Field(
        ..., description="Clientes em outros ramos que permaneceram com enlace ativo"
    )
    previously_disconnected_count: int = Field(
        ..., description="Clientes que já se encontravam desconectados antes do evento"
    )
    unknown_status_count: int = Field(
        ...,
        description="Clientes com documentação incompleta cujo impacto não pôde ser determinado",
    )
    impacted_ctos: list[str] = Field(..., description="Lista de códigos de CTOs afetadas")
    impacted_pon_ports: list[str] = Field(..., description="Portas PON afetadas pelo rompimento")
