from typing import Any

from fastapi import APIRouter, Query

from app.core.contracts import pending_endpoint
from app.schemas.geojson import MapFeatureCollection

map_router = APIRouter(prefix="/map", tags=["Mapa e Camadas GIS"])


@map_router.get(
    "/features",
    response_model=MapFeatureCollection,
    summary="Consultar feições espaciais para o mapa",
    description=(
        "Retorna uma FeatureCollection GeoJSON indexada por Bounding Box (minLon,minLat,maxLon,maxLat). "
        "Se o volume de geometrias exceder o limite seguro, truncated=true é retornado."
    ),
)
def get_map_features(
    bbox: str = Query(
        ...,
        description="Envelope geográfico no formato minLon,minLat,maxLon,maxLat em EPSG:4326",
        examples=["-46.64,-23.56,-46.62,-23.54"],
    ),
    layers: str | None = Query(
        default="sites,structures,cables",
        description="Camadas separadas por vírgula a serem renderizadas",
    ),
    zoom: int | None = Query(default=14, ge=0, le=24, description="Nível de zoom do cliente"),
) -> Any:
    pending_endpoint("B05")
