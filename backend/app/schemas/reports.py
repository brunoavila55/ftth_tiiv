from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CTOOccupancyBuckets(BaseModel):
    empty_0_pct: int = Field(default=0, description="CTOs com 0% das portas ocupadas")
    low_1_to_50_pct: int = Field(default=0, description="CTOs com 1% a 50% de ocupação")
    high_51_to_99_pct: int = Field(default=0, description="CTOs com 51% a 99% de ocupação")
    full_100_pct: int = Field(default=0, description="CTOs com 100% de ocupação (esgotadas)")


class DashboardSummaryResponse(BaseModel):
    total_sites: int
    total_structures: int
    total_cables: int
    total_customers: int
    total_active_service_links: int
    ctos_occupancy: CTOOccupancyBuckets
    incomplete_documentation_alerts: list[str] = Field(
        default_factory=list,
        description="Alertas de ativos com dados técnicos faltantes (ex: cabo sem comprimento medido)",
    )
    topology_revision: int


class SearchResultItem(BaseModel):
    id: str
    entity_type: str = Field(
        ..., description="Tipo de recurso (site, structure, cable, customer, device)"
    )
    code: str
    name: str | None = None
    status: str | None = None


class SearchGroup(BaseModel):
    entity_type: str
    items: list[SearchResultItem]


class GlobalSearchResponse(BaseModel):
    query: str
    total_results: int
    groups: list[SearchGroup]


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_id: str | None = None
    actor_name: str
    action: str = Field(
        ..., description="Ação auditada: CREATE, UPDATE, DELETE, CONNECT, DISCONNECT, etc."
    )
    entity_type: str
    entity_id: str
    changes: dict[str, Any] = Field(
        default_factory=dict, description="Dicionário sanitizado com valores antes e depois"
    )
    reason: str | None = None
    request_id: str | None = None
    created_at: datetime


class CTOOccupancyReportItem(BaseModel):
    structure_id: str
    code: str
    site_id: str | None = None
    site_name: str | None = None
    total_ports: int
    occupied_ports: int
    reserved_ports: int
    free_ports: int
    occupancy_pct: float
    status: str


class CableCapacityReportItem(BaseModel):
    cable_id: str
    code: str
    model: str | None = None
    cable_type: str
    total_fibers: int
    connected_fibers: int
    reserved_fibers: int
    free_fibers: int
    damaged_fibers: int
    usage_pct: float
    status: str


class InconsistencyReportItem(BaseModel):
    inconsistency_type: str
    entity_type: str
    entity_id: str
    code: str
    severity: str = Field(..., description="critical, warning, info")
    description: str
