import math
from typing import Any

from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import (  # type: ignore[import-untyped]
    LineString as ShapelyLineString,
)
from shapely.geometry import (
    Point as ShapelyPoint,
)

from app.core.errors import UnprocessableEntityError
from app.schemas.geojson import LineStringGeometry, PointGeometry

EARTH_RADIUS_METERS = 6371008.8  # Raio médio volumétrico da Terra (IUGG / WGS84)
MAX_LINESTRING_VERTICES = 10000


def validate_coordinates(
    lon: float,
    lat: float,
    field: str = "location.coordinates",
) -> None:
    """Valida se as coordenadas estão dentro dos limites geodésicos do WGS84 / EPSG:4326."""
    if math.isnan(lon) or math.isinf(lon):
        raise UnprocessableEntityError(
            f"Longitude inválida (NaN ou Infinito): {lon}.",
            field=f"{field}[0]",
        )
    if math.isnan(lat) or math.isinf(lat):
        raise UnprocessableEntityError(
            f"Latitude inválida (NaN ou Infinito): {lat}.",
            field=f"{field}[1]",
        )
    if not -180.0 <= lon <= 180.0:
        raise UnprocessableEntityError(
            f"Longitude inválida: {lon}. Deve estar no intervalo [-180.0, 180.0].",
            field=f"{field}[0]",
        )
    if not -90.0 <= lat <= 90.0:
        raise UnprocessableEntityError(
            f"Latitude inválida: {lat}. Deve estar no intervalo [-90.0, 90.0].",
            field=f"{field}[1]",
        )


def validate_linestring(
    coordinates: list[tuple[float, float]],
    field: str = "geometry.coordinates",
) -> None:
    """Valida lista de coordenadas de uma LineString GeoJSON conforme requisitos B05."""
    if not coordinates:
        raise UnprocessableEntityError(
            "A geometria LineString não pode ser vazia.",
            field=field,
        )
    if len(coordinates) < 2:
        raise UnprocessableEntityError(
            f"LineString inválida: requer no mínimo 2 vértices, fornecidos {len(coordinates)}.",
            field=field,
        )
    if len(coordinates) > MAX_LINESTRING_VERTICES:
        raise UnprocessableEntityError(
            f"LineString excede o limite máximo permitido de {MAX_LINESTRING_VERTICES} vértices.",
            field=field,
        )

    for i, (lon, lat) in enumerate(coordinates):
        validate_coordinates(lon, lat, field=f"{field}[{i}]")

    # Verifica se todos os vértices são idênticos (linha colapsada em ponto)
    first_pt = coordinates[0]
    if all(pt == first_pt for pt in coordinates):
        raise UnprocessableEntityError(
            "LineString degenerada: todos os vértices possuem coordenadas idênticas.",
            field=field,
        )


def parse_and_validate_bbox(bbox_str: str) -> tuple[float, float, float, float]:
    """Valida e extrai o envelope geográfico min_lon, min_lat, max_lon, max_lat."""
    parts = bbox_str.strip().split(",")
    if len(parts) != 4:
        raise UnprocessableEntityError(
            f"Formato de bbox inválido: '{bbox_str}'. Esperado: 'minLon,minLat,maxLon,maxLat'.",
            field="bbox",
        )

    try:
        min_lon = float(parts[0].strip())
        min_lat = float(parts[1].strip())
        max_lon = float(parts[2].strip())
        max_lat = float(parts[3].strip())
    except ValueError as err:
        raise UnprocessableEntityError(
            f"Valores numéricos inválidos na bbox: '{bbox_str}'.",
            field="bbox",
        ) from err

    validate_coordinates(min_lon, min_lat, field="bbox[min]")
    validate_coordinates(max_lon, max_lat, field="bbox[max]")

    if min_lon > max_lon:
        raise UnprocessableEntityError(
            f"Envelope bbox inválido: minLon ({min_lon}) não pode ser maior que maxLon ({max_lon}).",
            field="bbox",
        )
    if min_lat > max_lat:
        raise UnprocessableEntityError(
            f"Envelope bbox inválido: minLat ({min_lat}) não pode ser maior que maxLat ({max_lat}).",
            field="bbox",
        )

    return (min_lon, min_lat, max_lon, max_lat)


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


def linestring_geometry_to_wkb(line: LineStringGeometry) -> WKBElement:
    """Converte schema LineStringGeometry para elemento WKB PostGIS SRID 4326."""
    validate_linestring(line.coordinates)
    shapely_line = ShapelyLineString(line.coordinates)
    return from_shape(shapely_line, srid=4326)


def wkb_to_linestring_geometry(geom: Any) -> LineStringGeometry:
    """Converte elemento geométrico PostGIS (WKBElement ou Shape) para LineStringGeometry."""
    if isinstance(geom, ShapelyLineString):
        coords = [(float(x), float(y)) for x, y in geom.coords]
        return LineStringGeometry(type="LineString", coordinates=coords)
    shape = to_shape(geom)
    coords = [(float(x), float(y)) for x, y in shape.coords]
    return LineStringGeometry(type="LineString", coordinates=coords)


def haversine_distance_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Calcula a distância geodésica entre duas coordenadas WGS84 em metros (fórmula Haversine)."""
    lon1, lat1 = p1
    lon2, lat2 = p2

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def calculate_linestring_geodetic_length_m(coords: list[tuple[float, float]]) -> float:
    """Calcula o comprimento total geodésico de uma linha de coordenadas em metros."""
    if len(coords) < 2:
        return 0.0
    total_m = 0.0
    for i in range(len(coords) - 1):
        total_m += haversine_distance_m(coords[i], coords[i + 1])
    return total_m


def resolve_optical_length(
    map_length_m: float,
    measured_length_m: float | None = None,
    slack_length_m: float = 0.0,
) -> tuple[float, str]:
    """Aplica a regra de comprimento óptico confiável do FTTH Manager.

    Regra B05:
    - Se measured_length_m for informado, ele já representa o comprimento total instalado no campo.
      A reserva técnica (slack_length_m) NÃO deve ser somada novamente para evitar contagem dupla.
    - Se measured_length_m for None, o comprimento efetivo é map_length_m + slack_length_m.
    - Retorna (effective_length_m, length_source), onde length_source é 'measured' ou 'calculated'.
    """
    if measured_length_m is not None:
        return (round(float(measured_length_m), 2), "measured")
    return (round(float(map_length_m + slack_length_m), 2), "calculated")


def validate_route_endpoints_tolerance(
    linestring_coords: list[tuple[float, float]],
    origin_coords: tuple[float, float],
    destination_coords: tuple[float, float],
    tolerance_m: float = 5.0,
) -> None:
    """Valida a tolerância entre as extremidades da rota do cabo e os locais de acesso (estruturas).

    Se a distância da ponta inicial à estrutura de origem ou da ponta final à estrutura de destino
    exceder a tolerância configurada (padrão 5.0m), levanta UnprocessableEntityError exigindo
    correção explícita da geometria.
    """
    if not linestring_coords:
        raise UnprocessableEntityError("Coordenadas da rota vazias.", field="geometry.coordinates")

    start_pt = linestring_coords[0]
    end_pt = linestring_coords[-1]

    dist_start = haversine_distance_m(start_pt, origin_coords)
    if dist_start > tolerance_m:
        raise UnprocessableEntityError(
            f"Divergência na extremidade inicial da rota: distância de {dist_start:.2f}m "
            f"até a estrutura de origem excede a tolerância de {tolerance_m:.1f}m. "
            "Ajuste as coordenadas da extremidade do cabo para coincidir com a estrutura de acesso.",
            field="geometry.coordinates[0]",
        )

    dist_end = haversine_distance_m(end_pt, destination_coords)
    if dist_end > tolerance_m:
        raise UnprocessableEntityError(
            f"Divergência na extremidade final da rota: distância de {dist_end:.2f}m "
            f"até a estrutura de destino excede a tolerância de {tolerance_m:.1f}m. "
            "Ajuste as coordenadas da extremidade do cabo para coincidir com a estrutura de acesso.",
            field="geometry.coordinates[-1]",
        )
