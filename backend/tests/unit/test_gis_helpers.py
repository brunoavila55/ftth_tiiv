import math

import pytest

from app.core.errors import UnprocessableEntityError
from app.modules.gis.helpers import (
    calculate_linestring_geodetic_length_m,
    haversine_distance_m,
    parse_and_validate_bbox,
    resolve_optical_length,
    validate_coordinates,
    validate_linestring,
    validate_route_endpoints_tolerance,
)


def test_validate_coordinates_valid() -> None:
    # Coordenadas válidas de São Paulo
    validate_coordinates(-46.633308, -23.550520)
    # Limites estritos
    validate_coordinates(-180.0, -90.0)
    validate_coordinates(180.0, 90.0)
    validate_coordinates(0.0, 0.0)


def test_validate_coordinates_invalid() -> None:
    # Longitude fora dos limites
    with pytest.raises(UnprocessableEntityError) as exc_info:
        validate_coordinates(-180.1, 0.0)
    assert "Longitude inválida" in exc_info.value.detail
    assert exc_info.value.field == "location.coordinates[0]"

    # Latitude fora dos limites
    with pytest.raises(UnprocessableEntityError) as exc_info:
        validate_coordinates(0.0, 90.1)
    assert "Latitude inválida" in exc_info.value.detail
    assert exc_info.value.field == "location.coordinates[1]"

    # NaN e Inf
    with pytest.raises(UnprocessableEntityError):
        validate_coordinates(float("nan"), -23.5)
    with pytest.raises(UnprocessableEntityError):
        validate_coordinates(-46.6, float("inf"))


def test_validate_linestring_valid() -> None:
    coords: list[tuple[float, float]] = [
        (-46.633308, -23.550520),
        (-46.634120, -23.551200),
        (-46.635000, -23.552000),
    ]
    validate_linestring(coords)


def test_validate_linestring_invalid() -> None:
    # Linha vazia
    with pytest.raises(UnprocessableEntityError) as exc:
        validate_linestring([])
    assert "não pode ser vazia" in exc.value.detail

    # Menos de 2 vértices
    with pytest.raises(UnprocessableEntityError) as exc:
        validate_linestring([(-46.6, -23.5)])
    assert "requer no mínimo 2 vértices" in exc.value.detail

    # Vértices degenerados (todos colapsados no mesmo ponto)
    with pytest.raises(UnprocessableEntityError) as exc:
        validate_linestring([(-46.6, -23.5), (-46.6, -23.5)])
    assert "LineString degenerada" in exc.value.detail

    # Coordenada inválida dentro da lista
    with pytest.raises(UnprocessableEntityError) as exc:
        validate_linestring([(-46.6, -23.5), (200.0, -23.5)])
    assert "Longitude inválida" in exc.value.detail
    assert exc.value.field == "geometry.coordinates[1][0]"


def test_parse_and_validate_bbox_valid() -> None:
    bbox_str = "-46.64,-23.56,-46.62,-23.54"
    min_lon, min_lat, max_lon, max_lat = parse_and_validate_bbox(bbox_str)
    assert min_lon == -46.64
    assert min_lat == -23.56
    assert max_lon == -46.62
    assert max_lat == -23.54


def test_parse_and_validate_bbox_invalid() -> None:
    # Menos de 4 partes
    with pytest.raises(UnprocessableEntityError):
        parse_and_validate_bbox("-46.64,-23.56")

    # Valores não numéricos
    with pytest.raises(UnprocessableEntityError):
        parse_and_validate_bbox("-46.64,foo,-46.62,-23.54")

    # min_lon > max_lon
    with pytest.raises(UnprocessableEntityError) as exc:
        parse_and_validate_bbox("-46.60,-23.56,-46.62,-23.54")
    assert "minLon (-46.6) não pode ser maior que maxLon (-46.62)" in exc.value.detail

    # min_lat > max_lat
    with pytest.raises(UnprocessableEntityError) as exc:
        parse_and_validate_bbox("-46.64,-23.50,-46.62,-23.54")
    assert "minLat (-23.5) não pode ser maior que maxLat (-23.54)" in exc.value.detail


def test_haversine_distance_and_linestring_length() -> None:
    # Distância conhecida aproximada entre a Praça da Sé (-46.6333, -23.5505)
    # e a Av. Paulista / MASP (-46.6558, -23.5614): ~2.6 km
    p1 = (-46.6333, -23.5505)
    p2 = (-46.6558, -23.5614)
    dist = haversine_distance_m(p1, p2)
    assert 2500 < dist < 2700

    # Distância entre pontos idênticos deve ser 0
    assert haversine_distance_m(p1, p1) == 0.0

    # Comprimento geodésico da linha
    coords = [p1, p2]
    total_len = calculate_linestring_geodetic_length_m(coords)
    assert math.isclose(total_len, dist, rel_tol=1e-5)


def test_resolve_optical_length_rule() -> None:
    # Cenário 1: Sem medição no campo -> effective = map_length_m + slack_length_m
    effective, source = resolve_optical_length(
        map_length_m=150.0,
        measured_length_m=None,
        slack_length_m=20.0,
    )
    assert effective == 170.0
    assert source == "calculated"

    # Cenário 2: Com medição no campo -> effective = measured_length_m (reserva NÃO é somada novamente)
    effective_m, source_m = resolve_optical_length(
        map_length_m=150.0,
        measured_length_m=165.5,
        slack_length_m=20.0,
    )
    assert effective_m == 165.5
    assert source_m == "measured"


def test_validate_route_endpoints_tolerance() -> None:
    # Origem e destino
    origin = (-46.633308, -23.550520)
    dest = (-46.634120, -23.551200)

    # Linha perfeitamente alinhada com as estruturas
    valid_line = [origin, dest]
    validate_route_endpoints_tolerance(valid_line, origin, dest, tolerance_m=5.0)

    # Linha com ponta inicial distante 20 metros da origem
    # 0.0002 graus de latitude ~ 22.2 metros
    divergent_start = (-46.633308, -23.550520 + 0.0002)
    with pytest.raises(UnprocessableEntityError) as exc:
        validate_route_endpoints_tolerance([divergent_start, dest], origin, dest, tolerance_m=5.0)
    assert "Divergência na extremidade inicial da rota" in exc.value.detail
    assert exc.value.field == "geometry.coordinates[0]"

    # Linha com ponta final distante da estrutura de destino
    divergent_end = (-46.634120, -23.551200 + 0.0002)
    with pytest.raises(UnprocessableEntityError) as exc:
        validate_route_endpoints_tolerance([origin, divergent_end], origin, dest, tolerance_m=5.0)
    assert "Divergência na extremidade final da rota" in exc.value.detail
    assert exc.value.field == "geometry.coordinates[-1]"
