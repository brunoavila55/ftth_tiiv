from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import cast, func, select, text
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.modules.cables.models import Cable, CableSegment
from app.modules.gis.helpers import (
    parse_and_validate_bbox,
    wkb_to_linestring_geometry,
    wkb_to_point_geometry,
)
from app.modules.inventory.models import Site, Structure
from app.modules.topology.models import NetworkTopologyState
from app.schemas.geojson import FeatureProperties, MapFeature, MapFeatureCollection


def get_topology_revision(db: Session) -> int:
    """Retorna o número atual da revisão monotônica da topologia da rede."""
    state = db.execute(
        select(NetworkTopologyState).where(NetworkTopologyState.id == 1)
    ).scalar_one_or_none()

    if state is None:
        new_state = NetworkTopologyState(id=1, topology_revision=1)
        db.add(new_state)
        db.flush()
        return 1

    return int(state.topology_revision)


def bump_topology_revision(db: Session) -> int:
    """Incrementa atomicamente a revisão monotônica da topologia da rede e retorna o novo valor."""
    stmt = text(
        "UPDATE network_topology_state "
        "SET topology_revision = topology_revision + 1, updated_at = NOW() "
        "WHERE id = 1 "
        "RETURNING topology_revision;"
    )
    result = db.execute(stmt).scalar_one_or_none()
    if result is None:
        # Se a linha 1 ainda não existia, insere com revisão 2 (1 inicial + 1 bump)
        insert_stmt = text(
            "INSERT INTO network_topology_state (id, topology_revision, updated_at) "
            "VALUES (1, 2, NOW()) "
            "RETURNING topology_revision;"
        )
        result = db.execute(insert_stmt).scalar_one()
    return int(result)


def calculate_postgis_length_m(db: Session, geom_wkb: WKBElement) -> float:
    """Calcula o comprimento geodésico exato em metros via PostGIS geography (WGS84 spheroid)."""
    # ST_Length(cast(geom, geography)) calcula distância em metros sobre o elipsoide WGS84
    stmt = select(func.ST_Length(cast(geom_wkb, Geography)))
    length_m = db.execute(stmt).scalar_one()
    return round(float(length_m), 2)


def calculate_postgis_distance_m(
    db: Session, geom_wkb1: WKBElement, geom_wkb2: WKBElement
) -> float:
    """Calcula a distância geodésica exata entre dois pontos em metros via PostGIS geography."""
    stmt = select(func.ST_Distance(cast(geom_wkb1, Geography), cast(geom_wkb2, Geography)))
    dist_m = db.execute(stmt).scalar_one()
    return round(float(dist_m), 2)


def query_map_features(
    db: Session,
    bbox_str: str,
    layers_str: str | None = None,
    zoom: int | None = 14,
    limit: int | None = None,
) -> MapFeatureCollection:
    """Executa consulta espacial indexada por Bounding Box retornando FeatureCollection GeoJSON.

    - Valida o envelope geográfico bbox (minLon,minLat,maxLon,maxLat) em EPSG:4326.
    - Utiliza o índice GiST via ST_MakeEnvelope e operador de interseção espacial.
    - Suporta camadas: sites, structures, cables.
    - Se a quantidade de feições exceder o limite configurado (MAP_MAX_FEATURES),
      trunca a lista e sinaliza explicitamente com truncated=True.
    - Retorna a revisão topológica global atual.
    """
    settings = get_settings()
    max_limit = limit if limit is not None else settings.MAP_MAX_FEATURES

    min_lon, min_lat, max_lon, max_lat = parse_and_validate_bbox(bbox_str)

    # Cria envelope PostGIS SRID 4326
    envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)

    layers: set[str] = set()
    if layers_str:
        layers = {layer.strip().lower() for layer in layers_str.split(",") if layer.strip()}
    else:
        layers = {"sites", "structures", "cables"}

    features: list[MapFeature] = []

    # 1. Camada de Sites (POPs)
    if "sites" in layers:
        site_stmt = (
            select(Site)
            .where(Site.status != "retired", func.ST_Intersects(Site.location, envelope))
            .order_by(Site.code)
            .limit(max_limit + 1)
        )
        sites = db.execute(site_stmt).scalars().all()
        for s in sites:
            pt = wkb_to_point_geometry(s.location)
            props = FeatureProperties(
                entity_id=str(s.id),
                entity_type="site",
                code=s.code,
                status=s.status,
                version=s.version,
                extra={
                    "name": s.name,
                    "kind": s.kind,
                    "address": s.address,
                },
            )
            features.append(MapFeature(id=f"site:{s.id}", geometry=pt, properties=props))

    # 2. Camada de Estruturas (Postes, CEOs, CTOs)
    if "structures" in layers and len(features) <= max_limit:
        remaining = max_limit + 1 - len(features)
        struct_stmt = (
            select(Structure)
            .where(
                Structure.status != "retired",
                func.ST_Intersects(Structure.location, envelope),
            )
            .order_by(Structure.code)
            .limit(remaining)
        )
        structures = db.execute(struct_stmt).scalars().all()
        for st in structures:
            pt = wkb_to_point_geometry(st.location)
            props = FeatureProperties(
                entity_id=str(st.id),
                entity_type="structure",
                code=st.code,
                status=st.status,
                version=st.version,
                extra={
                    "kind": st.kind,
                    "site_id": str(st.site_id) if st.site_id else None,
                    "capacity": st.capacity,
                    "condition": st.condition,
                },
            )
            features.append(MapFeature(id=f"structure:{st.id}", geometry=pt, properties=props))

    # 3. Camada de Cabos (Cable Segments)
    if "cables" in layers and len(features) <= max_limit:
        remaining = max_limit + 1 - len(features)
        segment_stmt = (
            select(CableSegment)
            .options(
                joinedload(CableSegment.cable),
                joinedload(CableSegment.origin_structure),
                joinedload(CableSegment.destination_structure),
            )
            .where(func.ST_Intersects(CableSegment.geometry, envelope))
            .where(
                CableSegment.status != "retired",
                CableSegment.cable.has(Cable.status != "retired"),
            )
            .order_by(CableSegment.created_at)
            .limit(remaining)
        )
        segments = db.execute(segment_stmt).scalars().all()
        for seg in segments:
            line = wkb_to_linestring_geometry(seg.geometry)
            cable_code = seg.cable.code if seg.cable else str(seg.cable_id)
            props = FeatureProperties(
                entity_id=str(seg.id),
                entity_type="cable_segment",
                code=cable_code,
                status=seg.status,
                version=seg.version,
                extra={
                    "cable_id": str(seg.cable_id),
                    "origin_structure_id": str(seg.origin_structure_id),
                    "destination_structure_id": str(seg.destination_structure_id),
                    "model": seg.cable.model if seg.cable else None,
                    "fiber_count": seg.cable.fiber_count if seg.cable else None,
                    "tube_count": seg.cable.tube_count if seg.cable else None,
                    "origin_code": (seg.origin_structure.code if seg.origin_structure else None),
                    "destination_code": (
                        seg.destination_structure.code if seg.destination_structure else None
                    ),
                    "map_length_m": seg.map_length_m,
                    "measured_length_m": seg.measured_length_m,
                    "slack_length_m": seg.slack_length_m,
                    "effective_length_m": seg.effective_length_m,
                    "length_source": seg.length_source,
                },
            )
            features.append(
                MapFeature(id=f"cable_segment:{seg.id}", geometry=line, properties=props)
            )

    # Verificação estrita de truncamento (não truncar silenciosamente)
    truncated = False
    if len(features) > max_limit:
        features = features[:max_limit]
        truncated = True

    current_rev = get_topology_revision(db)

    return MapFeatureCollection(
        type="FeatureCollection",
        features=features,
        bbox=[min_lon, min_lat, max_lon, max_lat],
        topology_revision=current_rev,
        truncated=truncated,
    )
