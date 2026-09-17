import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    UnprocessableEntityError,
)
from app.modules.cables.models import Cable, CableSegment
from app.modules.gis.helpers import (
    linestring_geometry_to_wkb,
    resolve_optical_length,
    validate_linestring,
    validate_route_endpoints_tolerance,
    wkb_to_linestring_geometry,
    wkb_to_point_geometry,
)
from app.modules.gis.service import bump_topology_revision, calculate_postgis_length_m
from app.modules.inventory.models import Structure
from app.schemas.cables import (
    CableCreate,
    CableSegmentCreate,
    CableSegmentRead,
    CableSegmentUpdate,
    LengthSource,
)


def _check_optimistic_lock(current_version: int, if_match: str | None) -> None:
    """Valida precondição de concorrência otimista (If-Match) conforme RFC 7232."""
    if not if_match:
        raise PreconditionRequiredError(
            "Cabeçalho If-Match é obrigatório para operações de modificação."
        )
    clean_match = if_match.strip().strip('"').strip("'")
    try:
        expected_version = int(clean_match)
    except ValueError as err:
        raise PreconditionFailedError(
            f"Valor de If-Match inválido: '{if_match}'. Esperado um número inteiro de versão."
        ) from err

    if current_version != expected_version:
        raise PreconditionFailedError(
            f"Conflito de versão concorrente: a versão atual é {current_version}, mas If-Match forneceu {expected_version}."
        )


def create_cable(db: Session, payload: CableCreate) -> Cable:
    """Cria um novo cabo óptico."""
    existing = db.execute(select(Cable).where(Cable.code == payload.code)).scalar_one_or_none()
    if existing:
        raise UnprocessableEntityError(
            f"Já existe um cabo cadastrado com o código '{payload.code}'.",
            field="code",
        )

    cable = Cable(
        code=payload.code,
        model=payload.model,
        fiber_count=payload.fiber_count,
        tube_count=payload.tube_count,
        color_standard=payload.color_standard,
        status=payload.status.value,
        notes=payload.notes,
        version=1,
    )
    db.add(cable)
    db.commit()
    db.refresh(cable)
    return cable


def get_cable_by_id(db: Session, cable_id: str) -> Cable:
    """Obtém um cabo óptico por UUID."""
    try:
        c_uuid = uuid.UUID(cable_id)
    except ValueError as err:
        raise NotFoundError(f"Cabo com ID '{cable_id}' não encontrado.") from err

    cable = db.execute(select(Cable).where(Cable.id == c_uuid)).scalar_one_or_none()
    if not cable:
        raise NotFoundError(f"Cabo com ID '{cable_id}' não encontrado.")
    return cable


def create_cable_segment(db: Session, payload: CableSegmentCreate) -> CableSegment:
    """Cria um trecho de cabo ligando duas estruturas com validação geodésica e óptica."""
    # 1. Valida existência do cabo
    try:
        cable_uuid = uuid.UUID(payload.cable_id)
    except ValueError as err:
        raise UnprocessableEntityError(
            f"UUID de cabo inválido: '{payload.cable_id}'.", field="cable_id"
        ) from err
    cable = db.execute(select(Cable).where(Cable.id == cable_uuid)).scalar_one_or_none()
    if not cable:
        raise NotFoundError(f"Cabo '{payload.cable_id}' não encontrado.")

    # 2. Valida estruturas de origem e destino
    try:
        origin_uuid = uuid.UUID(payload.origin_structure_id)
        dest_uuid = uuid.UUID(payload.destination_structure_id)
    except ValueError as err:
        raise UnprocessableEntityError("UUID de estrutura inválido.", field="structure_id") from err

    if origin_uuid == dest_uuid:
        raise UnprocessableEntityError(
            "As estruturas de origem e destino do trecho de cabo devem ser distintas.",
            field="destination_structure_id",
        )

    origin_struct = db.execute(
        select(Structure).where(Structure.id == origin_uuid)
    ).scalar_one_or_none()
    if not origin_struct:
        raise NotFoundError(f"Estrutura de origem '{payload.origin_structure_id}' não encontrada.")

    dest_struct = db.execute(
        select(Structure).where(Structure.id == dest_uuid)
    ).scalar_one_or_none()
    if not dest_struct:
        raise NotFoundError(
            f"Estrutura de destino '{payload.destination_structure_id}' não encontrada."
        )

    # 3. Validação geométrica e tolerância com as estruturas
    validate_linestring(payload.geometry.coordinates)
    origin_pt = wkb_to_point_geometry(origin_struct.location).coordinates
    dest_pt = wkb_to_point_geometry(dest_struct.location).coordinates

    settings = get_settings()
    validate_route_endpoints_tolerance(
        linestring_coords=payload.geometry.coordinates,
        origin_coords=origin_pt,
        destination_coords=dest_pt,
        tolerance_m=settings.ROUTE_ENDPOINT_TOLERANCE_M,
    )

    # 4. Cálculo de comprimento geodésico via PostGIS em metros
    geom_wkb = linestring_geometry_to_wkb(payload.geometry)
    map_length_m = calculate_postgis_length_m(db, geom_wkb)

    # 5. Aplicação da regra óptica de comprimento
    effective_length_m, length_source = resolve_optical_length(
        map_length_m=map_length_m,
        measured_length_m=payload.measured_length_m,
        slack_length_m=payload.slack_length_m,
    )

    # 6. Criação do trecho e incremento atômico da revisão topológica
    segment = CableSegment(
        cable_id=cable_uuid,
        origin_structure_id=origin_uuid,
        destination_structure_id=dest_uuid,
        geometry=geom_wkb,
        map_length_m=map_length_m,
        measured_length_m=payload.measured_length_m,
        slack_length_m=payload.slack_length_m,
        effective_length_m=effective_length_m,
        length_source=length_source,
        version=1,
    )
    db.add(segment)

    # Atualização geométrica afeta cálculo óptico -> incrementa topology_revision
    bump_topology_revision(db)

    db.commit()
    db.refresh(segment)
    return segment


def get_cable_segment_by_id(db: Session, segment_id: str) -> CableSegment:
    """Obtém um trecho de cabo por UUID."""
    try:
        s_uuid = uuid.UUID(segment_id)
    except ValueError as err:
        raise NotFoundError(f"Trecho de cabo com ID '{segment_id}' não encontrado.") from err

    segment = db.execute(select(CableSegment).where(CableSegment.id == s_uuid)).scalar_one_or_none()
    if not segment:
        raise NotFoundError(f"Trecho de cabo com ID '{segment_id}' não encontrado.")
    return segment


def update_cable_segment(
    db: Session,
    segment_id: str,
    payload: CableSegmentUpdate,
    if_match: str | None,
) -> CableSegment:
    """Atualiza a geometria ou comprimentos de um trecho de cabo com controle de concorrência."""
    segment = get_cable_segment_by_id(db, segment_id)
    _check_optimistic_lock(segment.version, if_match)

    affects_calculation = False

    if payload.geometry is not None:
        validate_linestring(payload.geometry.coordinates)
        origin_struct = db.execute(
            select(Structure).where(Structure.id == segment.origin_structure_id)
        ).scalar_one()
        dest_struct = db.execute(
            select(Structure).where(Structure.id == segment.destination_structure_id)
        ).scalar_one()
        origin_pt = wkb_to_point_geometry(origin_struct.location).coordinates
        dest_pt = wkb_to_point_geometry(dest_struct.location).coordinates

        settings = get_settings()
        validate_route_endpoints_tolerance(
            linestring_coords=payload.geometry.coordinates,
            origin_coords=origin_pt,
            destination_coords=dest_pt,
            tolerance_m=settings.ROUTE_ENDPOINT_TOLERANCE_M,
        )

        geom_wkb = linestring_geometry_to_wkb(payload.geometry)
        segment.geometry = geom_wkb
        segment.map_length_m = calculate_postgis_length_m(db, geom_wkb)
        affects_calculation = True

    if payload.measured_length_m is not None:
        segment.measured_length_m = payload.measured_length_m
        affects_calculation = True

    if payload.slack_length_m is not None:
        segment.slack_length_m = payload.slack_length_m
        affects_calculation = True

    if affects_calculation:
        effective_len, source = resolve_optical_length(
            map_length_m=segment.map_length_m,
            measured_length_m=segment.measured_length_m,
            slack_length_m=segment.slack_length_m,
        )
        segment.effective_length_m = effective_len
        segment.length_source = source
        # Alteração geométrica ou de comprimentos afeta cálculo óptico -> bump topology_revision
        bump_topology_revision(db)

    segment.version += 1
    db.commit()
    db.refresh(segment)
    return segment


def cable_segment_to_schema(segment: CableSegment) -> CableSegmentRead:
    """Converte modelo CableSegment para schema CableSegmentRead."""
    return CableSegmentRead(
        id=str(segment.id),
        cable_id=str(segment.cable_id),
        origin_structure_id=str(segment.origin_structure_id),
        destination_structure_id=str(segment.destination_structure_id),
        geometry=wkb_to_linestring_geometry(segment.geometry),
        map_length_m=segment.map_length_m,
        measured_length_m=segment.measured_length_m,
        slack_length_m=segment.slack_length_m,
        effective_length_m=segment.effective_length_m,
        length_source=LengthSource(segment.length_source),
        version=segment.version,
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )
