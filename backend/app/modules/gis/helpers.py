from typing import Any

from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point as ShapelyPoint  # type: ignore[import-untyped]

from app.core.errors import UnprocessableEntityError
from app.schemas.geojson import PointGeometry


def validate_coordinates(lon: float, lat: float) -> None:
    """Valida se as coordenadas estão dentro dos limites geodésicos do WGS84 / EPSG:4326."""
    if not -180.0 <= lon <= 180.0:
        raise UnprocessableEntityError(
            f"Longitude inválida: {lon}. Deve estar no intervalo [-180.0, 180.0].",
            field="location.coordinates[0]",
        )
    if not -90.0 <= lat <= 90.0:
        raise UnprocessableEntityError(
            f"Latitude inválida: {lat}. Deve estar no intervalo [-90.0, 90.0].",
            field="location.coordinates[1]",
        )


def point_geometry_to_wkb(point: PointGeometry) -> WKBElement:
    """Converte schema PointGeometry para elemento WKB PostGIS SRID 4326."""
    lon, lat = point.coordinates
    validate_coordinates(lon, lat)
    shapely_point = ShapelyPoint(lon, lat)
    return from_shape(shapely_point, srid=4326)


def wkb_to_point_geometry(geom: Any) -> PointGeometry:
    """Converte elemento geométrico PostGIS (WKBElement ou Shape) para PointGeometry."""
    if isinstance(geom, ShapelyPoint):
        return PointGeometry(type="Point", coordinates=(float(geom.x), float(geom.y)))
    shape = to_shape(geom)
    return PointGeometry(type="Point", coordinates=(float(shape.x), float(shape.y)))
