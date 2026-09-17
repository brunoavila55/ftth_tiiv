from typing import Any, Literal

from pydantic import BaseModel, Field


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float] = Field(
        ...,
        description="Coordenadas [longitude, latitude] em WGS84 / EPSG:4326",
        examples=[[-46.633308, -23.550520]],
    )


class LineStringGeometry(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]] = Field(
        ...,
        min_length=2,
        description="Lista de coordenadas [longitude, latitude] que formam a linha",
        examples=[[[-46.633308, -23.550520], [-46.634120, -23.551200]]],
    )


class FeatureProperties(BaseModel):
    entity_id: str = Field(..., description="UUID da entidade referenciada")
    entity_type: str = Field(..., description="Tipo da entidade (structure, cable_segment, etc.)")
    code: str = Field(..., description="Código humano legível da entidade")
    status: str = Field(..., description="Estado administrativo ou físico")
    version: int = Field(..., description="Versão de concorrência do recurso")
    occupancy: dict[str, int] | None = Field(
        default=None,
        description="Ocupação agregada para caixas/estruturas (ex: free, reserved, connected)",
    )
    extra: dict[str, Any] | None = Field(
        default=None,
        description="Metadados adicionais específicos da camada",
    )


class MapFeature(BaseModel):
    id: str = Field(..., description="Identificador único da feature no mapa")
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry | LineStringGeometry = Field(
        ..., description="Geometria GeoJSON da entidade"
    )
    properties: FeatureProperties = Field(..., description="Propriedades e atributos da feature")


class MapFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[MapFeature] = Field(..., description="Lista de features visíveis na bbox")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Envelope geográfico retornado [min_lon, min_lat, max_lon, max_lat]",
    )
    topology_revision: int = Field(
        ..., description="Revisão topológica da rede no momento da extração"
    )
    truncated: bool = Field(
        ...,
        description="Indica se o limite de features foi excedido exigindo maior aproximação",
    )
