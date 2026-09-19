import math
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.concurrency import check_if_match
from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    NotFoundError,
    PreconditionRequiredError,
    TopologyRevisionConflictError,
    UnprocessableEntityError,
)
from app.core.search import contains
from app.modules.cables.models import Cable, CableSegment, Fiber, FiberSegment, Tube
from app.modules.connectivity.models import Connection, ConnectionEndpoint, InternalEdge, Terminal
from app.modules.gis.helpers import (
    linestring_geometry_to_wkb,
    resolve_optical_length,
    split_linestring_at_point,
    validate_linestring,
    validate_route_endpoints_tolerance,
    wkb_to_linestring_geometry,
    wkb_to_point_geometry,
)
from app.modules.gis.service import (
    bump_topology_revision,
    calculate_postgis_length_m,
    get_topology_revision,
)
from app.modules.inventory.catalogs import get_color_standard
from app.modules.inventory.models import Structure
from app.schemas.cables import (
    CableCreate,
    CableRead,
    CableSegmentCreate,
    CableSegmentRead,
    CableSegmentUpdate,
    CableUpdate,
    FiberRead,
    FiberSegmentRead,
    LengthSource,
    SegmentSplitPreviewResponse,
    SegmentSplitRequest,
    SegmentSplitResponse,
    TubeRead,
)
from app.schemas.common import AdministrativeStatus, OccupancyStatus


def create_cable(db: Session, payload: CableCreate, commit: bool = True) -> Cable:
    """Cria transacionalmente um cabo óptico com seus tubos loose e fibras numeradas."""
    # 1. Unicidade do código
    existing = db.execute(select(Cable).where(Cable.code == payload.code)).scalar_one_or_none()
    if existing:
        raise UnprocessableEntityError(
            f"Já existe um cabo cadastrado com o código '{payload.code}'.",
            field="code",
        )

    # 2. Validação do padrão de cores
    color_palette = get_color_standard(payload.color_standard)
    if not color_palette:
        raise UnprocessableEntityError(
            f"Padrão de cores '{payload.color_standard}' inválido ou não suportado.",
            field="color_standard",
        )

    if payload.fiber_count < 1:
        raise UnprocessableEntityError(
            "A quantidade de fibras deve ser no mínimo 1.", field="fiber_count"
        )
    if payload.tube_count < 1:
        raise UnprocessableEntityError(
            "A quantidade de tubos deve ser no mínimo 1.", field="tube_count"
        )
    if payload.fiber_count < payload.tube_count:
        raise UnprocessableEntityError(
            "A quantidade de fibras não pode ser menor que a quantidade de tubos.",
            field="fiber_count",
        )

    # 3. Criação do cabeçalho do cabo
    cable = Cable(
        code=payload.code,
        model=payload.model,
        fiber_count=payload.fiber_count,
        tube_count=payload.tube_count,
        color_standard=payload.color_standard.upper(),
        status=payload.status.value,
        notes=payload.notes,
        version=1,
    )
    db.add(cable)
    db.flush()

    # 4. Geração transacional de tubos loose
    fibers_per_tube = math.ceil(payload.fiber_count / payload.tube_count)
    is_logical = payload.tube_count == 1 and payload.fiber_count > 12

    tubes: list[Tube] = []
    for t_idx in range(1, payload.tube_count + 1):
        color_name = color_palette[(t_idx - 1) % len(color_palette)]
        tube = Tube(
            cable_id=cable.id,
            number=t_idx,
            color_name=color_name,
            is_logical_group=is_logical,
            version=1,
        )
        db.add(tube)
        tubes.append(tube)

    db.flush()

    # 5. Geração transacional de fibras ópticas individuais
    global_fiber_num = 1
    for tube in tubes:
        fibers_in_this_tube = min(fibers_per_tube, payload.fiber_count - global_fiber_num + 1)
        for pos in range(1, fibers_in_this_tube + 1):
            fiber_color = color_palette[(pos - 1) % len(color_palette)]
            fiber = Fiber(
                cable_id=cable.id,
                tube_id=tube.id,
                global_number=global_fiber_num,
                tube_position=pos,
                color_name=fiber_color,
                status="installed",
                version=1,
            )
            db.add(fiber)
            global_fiber_num += 1

    if commit:
        db.commit()
        db.refresh(cable)
    else:  # chamador (ex.: importação em lote) controla a transação
        db.flush()
    return cable


def get_cable_by_id(db: Session, cable_id: str) -> Cable:
    """Obtém um cabo óptico por UUID com tubos e fibras carregados."""
    try:
        c_uuid = uuid.UUID(cable_id)
    except ValueError as err:
        raise NotFoundError(f"Cabo com ID '{cable_id}' não encontrado.") from err

    stmt = (
        select(Cable)
        .options(selectinload(Cable.tubes), selectinload(Cable.fibers))
        .where(Cable.id == c_uuid)
    )
    cable = db.execute(stmt).scalar_one_or_none()
    if not cable:
        raise NotFoundError(f"Cabo com ID '{cable_id}' não encontrado.")
    return cable


def list_cables(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    q: str | None = None,
) -> tuple[list[Cable], int]:
    """Lista cabos ópticos com busca textual e paginação."""
    query = select(Cable)
    if q:
        query = query.where(contains(Cable.code, q) | contains(Cable.model, q))

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = db.execute(query.order_by(Cable.code).limit(limit).offset(offset)).scalars().all()
    return list(items), total


def update_cable(
    db: Session,
    cable_id: str,
    payload: CableUpdate,
    if_match: str | None,
) -> Cable:
    """Atualiza metadados do cabo óptico com concorrência otimista."""
    cable = get_cable_by_id(db, cable_id)
    check_if_match(if_match, cable.version)

    if payload.status is not None:
        cable.status = payload.status.value
    if payload.notes is not None:
        cable.notes = payload.notes

    cable.version += 1
    db.commit()
    db.refresh(cable)
    return cable


def delete_cable(db: Session, cable_id: str, if_match: str | None) -> None:
    """Desativa ou remove um cabo óptico garantindo integridade referencial."""
    cable = get_cable_by_id(db, cable_id)
    check_if_match(if_match, cable.version)

    has_segments = db.execute(
        select(CableSegment.id).where(CableSegment.cable_id == cable.id).limit(1)
    ).scalar_one_or_none()
    if has_segments:
        raise ConflictError(
            f"Não é possível remover o cabo '{cable.code}' pois ele possui trechos físicos implantados.",
            code="cable_has_segments",
        )

    cable.status = "retired"
    cable.version += 1
    db.commit()


def create_cable_segment(
    db: Session,
    payload: CableSegmentCreate,
    commit: bool = True,
    bump_revision: bool = True,
) -> CableSegment:
    """Cria um trecho de cabo gerando 2 terminais ópticos (A e B) para cada fibra."""
    try:
        cable_uuid = uuid.UUID(payload.cable_id)
    except ValueError as err:
        raise UnprocessableEntityError(
            f"UUID de cabo inválido: '{payload.cable_id}'.", field="cable_id"
        ) from err

    stmt = select(Cable).options(selectinload(Cable.fibers)).where(Cable.id == cable_uuid)
    cable = db.execute(stmt).scalar_one_or_none()
    if not cable:
        raise NotFoundError(f"Cabo '{payload.cable_id}' não encontrado.")

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

    geom_wkb = linestring_geometry_to_wkb(payload.geometry)
    map_length_m = calculate_postgis_length_m(db, geom_wkb)

    effective_length_m, length_source = resolve_optical_length(
        map_length_m=map_length_m,
        measured_length_m=payload.measured_length_m,
        slack_length_m=payload.slack_length_m,
    )

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
    db.flush()

    # Gera 2 terminais ópticos por fibra (1 na origem e 1 no destino)
    for fiber in sorted(cable.fibers, key=lambda f: f.global_number):
        term_a = Terminal(
            kind="fiber_endpoint",
            structure_id=origin_uuid,
            label=f"{cable.code} - F{fiber.global_number} - Ponta A @ {origin_struct.code}",
            is_occupied=False,
            occupancy="free",
            entity_type="fiber",
            entity_id=fiber.id,
            version=1,
        )
        term_b = Terminal(
            kind="fiber_endpoint",
            structure_id=dest_uuid,
            label=f"{cable.code} - F{fiber.global_number} - Ponta B @ {dest_struct.code}",
            is_occupied=False,
            occupancy="free",
            entity_type="fiber",
            entity_id=fiber.id,
            version=1,
        )
        db.add_all([term_a, term_b])
        db.flush()

        fiber_seg = FiberSegment(
            cable_segment_id=segment.id,
            fiber_id=fiber.id,
            fiber_number=fiber.global_number,
            terminal_a_id=term_a.id,
            terminal_b_id=term_b.id,
            occupancy="free",
            version=1,
        )
        db.add(fiber_seg)
        db.flush()

        edge = InternalEdge(
            terminal_a_id=term_a.id,
            terminal_b_id=term_b.id,
            edge_type="fiber_continuity",
            entity_type="fiber_segment",
            entity_id=fiber_seg.id,
            loss_db=0.0,
            is_bidirectional=True,
            version=1,
        )
        db.add(edge)

    if bump_revision:  # o chamador em lote (importação) bumpa UMA vez, no fim da transação
        bump_topology_revision(db)
    if commit:
        db.commit()
        db.refresh(segment)
    else:
        db.flush()
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


def list_cable_segments(
    db: Session,
    limit: int = 20,
    offset: int = 0,
    cable_id: str | None = None,
) -> tuple[list[CableSegment], int]:
    """Lista trechos de cabos com filtro opcional por cabo e paginação."""
    query = select(CableSegment)
    if cable_id:
        try:
            c_uuid = uuid.UUID(cable_id)
            query = query.where(CableSegment.cable_id == c_uuid)
        except ValueError:
            return [], 0

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = (
        db.execute(query.order_by(CableSegment.created_at).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return list(items), total


def list_segment_fibers(
    db: Session,
    segment_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FiberSegment], int]:
    """Lista as fibras de um segmento de cabo com paginação."""
    segment = get_cable_segment_by_id(db, segment_id)
    query = select(FiberSegment).where(FiberSegment.cable_segment_id == segment.id)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = (
        db.execute(query.order_by(FiberSegment.fiber_number).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return list(items), total


def update_cable_segment(
    db: Session,
    segment_id: str,
    payload: CableSegmentUpdate,
    if_match: str | None,
) -> CableSegment:
    """Atualiza a geometria ou comprimentos de um trecho de cabo com controle de concorrência."""
    segment = get_cable_segment_by_id(db, segment_id)
    check_if_match(if_match, segment.version)

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
        bump_topology_revision(db)

    segment.version += 1
    db.commit()
    db.refresh(segment)
    return segment


def delete_cable_segment(db: Session, segment_id: str, if_match: str | None) -> None:
    """Desativa um trecho de cabo óptico."""
    segment = get_cable_segment_by_id(db, segment_id)
    check_if_match(if_match, segment.version)

    # Verifica se há conexões ativas nos terminais das fibras deste trecho
    stmt = (
        select(Connection.id)
        .join(
            FiberSegment,
            (Connection.terminal_a_id == FiberSegment.terminal_a_id)
            | (Connection.terminal_b_id == FiberSegment.terminal_b_id),
        )
        .where(FiberSegment.cable_segment_id == segment.id, Connection.is_active == True)  # noqa: E712
        .limit(1)
    )
    has_active_conn = db.execute(stmt).scalar_one_or_none()
    if has_active_conn:
        raise ConflictError(
            "Não é possível remover o trecho pois existem conexões ópticas ativas em suas fibras.",
            code="segment_has_active_connections",
        )

    segment.status = "retired"
    segment.version += 1
    bump_topology_revision(db)
    db.commit()


def preview_split_segment(
    db: Session,
    segment_id: str,
    payload: SegmentSplitRequest,
) -> SegmentSplitPreviewResponse:
    """Pré-visualiza o impacto da operação de divisão de trecho."""
    segment = get_cable_segment_by_id(db, segment_id)
    try:
        access_uuid = uuid.UUID(payload.access_structure_id)
    except ValueError as err:
        raise UnprocessableEntityError(
            "UUID de estrutura de acesso inválido.", field="access_structure_id"
        ) from err

    if access_uuid in (segment.origin_structure_id, segment.destination_structure_id):
        raise UnprocessableEntityError(
            "A estrutura de acesso não pode ser a própria origem ou destino do trecho.",
            field="access_structure_id",
        )

    access_struct = db.execute(
        select(Structure).where(Structure.id == access_uuid)
    ).scalar_one_or_none()
    if not access_struct:
        raise NotFoundError(f"Estrutura de acesso '{payload.access_structure_id}' não encontrada.")

    access_coords = wkb_to_point_geometry(access_struct.location).coordinates
    split_pt = payload.split_coordinates or access_coords

    orig_geom = wkb_to_linestring_geometry(segment.geometry)
    coords_1, coords_2 = split_linestring_at_point(orig_geom.coordinates, split_pt)

    wkb_1 = linestring_geometry_to_wkb(type(orig_geom)(coordinates=coords_1))
    wkb_2 = linestring_geometry_to_wkb(type(orig_geom)(coordinates=coords_2))
    len_1 = calculate_postgis_length_m(db, wkb_1)
    len_2 = calculate_postgis_length_m(db, wkb_2)

    fiber_segs = (
        db.execute(select(FiberSegment).where(FiberSegment.cable_segment_id == segment.id))
        .scalars()
        .all()
    )
    total_fibers = len(fiber_segs)

    cut_set = set(payload.cut_fiber_ids)
    cut_count = sum(1 for fs in fiber_segs if str(fs.fiber_id) in cut_set)
    pass_count = total_fibers - cut_count

    warnings: list[str] = []
    if cut_count == 0:
        warnings.append(
            "Nenhuma fibra foi selecionada para corte: todas serão mantidas em continuidade interna."
        )
    elif cut_count == total_fibers:
        warnings.append(
            "Todas as fibras serão cortadas nesta estrutura para emenda/fusão explícita."
        )

    return SegmentSplitPreviewResponse(
        original_segment_id=str(segment.id),
        access_structure_id=str(access_struct.id),
        total_fibers_count=total_fibers,
        cut_fibers_count=cut_count,
        pass_through_fibers_count=pass_count,
        segment_1_map_length_m=len_1,
        segment_2_map_length_m=len_2,
        warnings=warnings,
    )


def split_cable_segment(
    db: Session,
    segment_id: str,
    payload: SegmentSplitRequest,
    if_match: str | None = None,
) -> SegmentSplitResponse:
    """Executa a divisão atômica de um segmento em local de acesso intermediário.

    Regras B06:
    - Preserva a identidade do cabo e de cada fibra óptica.
    - Preserva as conexões externas ativas pré-existentes nas extremidades de origem e destino.
    - Para fibras passantes (não cortadas): cria continuidade interna (sem perda de fusão).
    - Para fibras cortadas: cria novas extremidades livres para emenda explícita na caixa.
    - Não duplica comprimentos nem reservas técnicas.
    - Toda a operação ocorre em uma única transação atômica (falha reverte tudo).

    Concorrência (EST-04): exige If-Match (versão do trecho) OU expected_topology_revision; a
    linha de estado da topologia e o trecho são travados (FOR UPDATE), então duas divisões do mesmo
    trecho nunca correm juntas — a segunda recebe 409/412/404 e nada é duplicado.
    """
    if payload.expected_topology_revision is None and (if_match is None or not if_match.strip()):
        raise PreconditionRequiredError(
            "Informe If-Match (versão do trecho) ou expected_topology_revision para dividir o trecho."
        )
    try:
        segment_uuid = uuid.UUID(segment_id)
    except ValueError as err:
        raise NotFoundError(f"Trecho de cabo com ID '{segment_id}' não encontrado.") from err

    # Serializa mutações de topologia: quem chega depois espera o commit de quem já está dividindo.
    # (SELECT ... FOR UPDATE devolve a revisão ATUAL após a espera; o objeto ORM cacheado ficaria velho.)
    get_topology_revision(db)  # garante que a linha de estado existe
    current_revision = int(
        db.execute(
            text("SELECT topology_revision FROM network_topology_state WHERE id = 1 FOR UPDATE")
        ).scalar_one()
    )
    if (
        payload.expected_topology_revision is not None
        and payload.expected_topology_revision != current_revision
    ):
        raise TopologyRevisionConflictError(
            detail=(
                f"A revisão topológica esperada ({payload.expected_topology_revision}) diverge da "
                f"revisão atual ({current_revision}). Recarregue a topologia antes de dividir."
            )
        )

    segment = db.execute(
        select(CableSegment).where(CableSegment.id == segment_uuid).with_for_update()
    ).scalar_one_or_none()
    if segment is None:
        raise NotFoundError(f"Trecho de cabo com ID '{segment_id}' não encontrado.")
    if if_match is not None and if_match.strip():
        check_if_match(if_match, segment.version)

    try:
        access_uuid = uuid.UUID(payload.access_structure_id)
    except ValueError as err:
        raise UnprocessableEntityError(
            "UUID de estrutura de acesso inválido.", field="access_structure_id"
        ) from err

    if access_uuid in (segment.origin_structure_id, segment.destination_structure_id):
        raise UnprocessableEntityError(
            "A estrutura de acesso intermediária não pode ser a própria origem ou destino do trecho.",
            field="access_structure_id",
        )

    access_struct = db.execute(
        select(Structure).where(Structure.id == access_uuid)
    ).scalar_one_or_none()
    if not access_struct:
        raise NotFoundError(f"Estrutura de acesso '{payload.access_structure_id}' não encontrada.")

    cable = db.execute(select(Cable).where(Cable.id == segment.cable_id)).scalar_one()

    access_coords = wkb_to_point_geometry(access_struct.location).coordinates
    split_pt = payload.split_coordinates or access_coords

    orig_geom = wkb_to_linestring_geometry(segment.geometry)
    coords_1, coords_2 = split_linestring_at_point(orig_geom.coordinates, split_pt)

    wkb_1 = linestring_geometry_to_wkb(type(orig_geom)(coordinates=coords_1))
    wkb_2 = linestring_geometry_to_wkb(type(orig_geom)(coordinates=coords_2))
    len_1 = calculate_postgis_length_m(db, wkb_1)
    len_2 = calculate_postgis_length_m(db, wkb_2)

    eff_len_1, src_1 = resolve_optical_length(len_1, None, payload.segment_1_slack_m)
    eff_len_2, src_2 = resolve_optical_length(len_2, None, payload.segment_2_slack_m)

    # Criação do primeiro novo trecho (Origem -> Acesso)
    seg_1 = CableSegment(
        cable_id=cable.id,
        origin_structure_id=segment.origin_structure_id,
        destination_structure_id=access_uuid,
        geometry=wkb_1,
        map_length_m=len_1,
        measured_length_m=None,
        slack_length_m=payload.segment_1_slack_m,
        effective_length_m=eff_len_1,
        length_source=src_1,
        version=1,
    )
    # Criação do segundo novo trecho (Acesso -> Destino)
    seg_2 = CableSegment(
        cable_id=cable.id,
        origin_structure_id=access_uuid,
        destination_structure_id=segment.destination_structure_id,
        geometry=wkb_2,
        map_length_m=len_2,
        measured_length_m=None,
        slack_length_m=payload.segment_2_slack_m,
        effective_length_m=eff_len_2,
        length_source=src_2,
        version=1,
    )
    db.add_all([seg_1, seg_2])
    db.flush()

    # Recupera todos os fiber_segments originais com terminais
    old_fiber_segs = (
        db.execute(
            select(FiberSegment)
            .where(FiberSegment.cable_segment_id == segment.id)
            .order_by(FiberSegment.fiber_number)
            .with_for_update()
        )
        .scalars()
        .all()
    )

    cut_set = set(payload.cut_fiber_ids)
    pass_through_count = 0
    cut_terminals_count = 0

    for old_fs in old_fiber_segs:
        is_cut = str(old_fs.fiber_id) in cut_set

        # Cria novos terminais no local de acesso intermediário
        term_1b = Terminal(
            kind="fiber_endpoint",
            structure_id=access_uuid,
            label=f"{cable.code} - F{old_fs.fiber_number} - Ponta B (Trecho 1) @ {access_struct.code}",
            is_occupied=False,
            occupancy="free",
            entity_type="fiber",
            entity_id=old_fs.fiber_id,
            version=1,
        )
        term_2a = Terminal(
            kind="fiber_endpoint",
            structure_id=access_uuid,
            label=f"{cable.code} - F{old_fs.fiber_number} - Ponta A (Trecho 2) @ {access_struct.code}",
            is_occupied=False,
            occupancy="free",
            entity_type="fiber",
            entity_id=old_fs.fiber_id,
            version=1,
        )
        db.add_all([term_1b, term_2a])
        db.flush()

        # Trecho 1: reusa terminal_a antigo (preserva conexões na origem) e novo terminal_1b no acesso
        fs_1 = FiberSegment(
            cable_segment_id=seg_1.id,
            fiber_id=old_fs.fiber_id,
            fiber_number=old_fs.fiber_number,
            terminal_a_id=old_fs.terminal_a_id,
            terminal_b_id=term_1b.id,
            occupancy="connected" if not is_cut else "free",
            version=1,
        )
        # Trecho 2: novo terminal_2a no acesso e reusa terminal_b antigo (preserva conexões no destino)
        fs_2 = FiberSegment(
            cable_segment_id=seg_2.id,
            fiber_id=old_fs.fiber_id,
            fiber_number=old_fs.fiber_number,
            terminal_a_id=term_2a.id,
            terminal_b_id=old_fs.terminal_b_id,
            occupancy="connected" if not is_cut else "free",
            version=1,
        )
        db.add_all([fs_1, fs_2])
        db.flush()

        # Adiciona as arestas internas dos novos segmentos
        edge_1 = InternalEdge(
            terminal_a_id=fs_1.terminal_a_id,
            terminal_b_id=fs_1.terminal_b_id,
            edge_type="fiber_continuity",
            entity_type="fiber_segment",
            entity_id=fs_1.id,
            loss_db=0.0,
            is_bidirectional=True,
            version=1,
        )
        edge_2 = InternalEdge(
            terminal_a_id=fs_2.terminal_a_id,
            terminal_b_id=fs_2.terminal_b_id,
            edge_type="fiber_continuity",
            entity_type="fiber_segment",
            entity_id=fs_2.id,
            loss_db=0.0,
            is_bidirectional=True,
            version=1,
        )
        db.add_all([edge_1, edge_2])

        if not is_cut:
            # Fibra passante: cria conexão de continuidade interna sem corte e sem perda adicional
            conn = Connection(
                terminal_a_id=term_1b.id,
                terminal_b_id=term_2a.id,
                connection_type="internal_continuity",
                loss_db=0.0,
                structure_id=access_uuid,
                is_active=True,
                notes="Continuidade interna de fibra passante gerada automaticamente na divisão",
                version=1,
            )
            db.add(conn)
            db.flush()

            ep_1 = ConnectionEndpoint(
                connection_id=conn.id,
                terminal_id=term_1b.id,
                is_active=True,
                version=1,
            )
            ep_2 = ConnectionEndpoint(
                connection_id=conn.id,
                terminal_id=term_2a.id,
                is_active=True,
                version=1,
            )
            db.add_all([ep_1, ep_2])

            term_1b.is_occupied = True
            term_1b.occupancy = "connected"
            term_2a.is_occupied = True
            term_2a.occupancy = "connected"
            pass_through_count += 1
        else:
            cut_terminals_count += 2

    # Remove os fiber_segments e internal_edges do trecho antigo
    for old_fs in old_fiber_segs:
        db.query(InternalEdge).filter(
            InternalEdge.entity_id == old_fs.id,
            InternalEdge.entity_type == "fiber_segment",
        ).delete(synchronize_session=False)
        db.delete(old_fs)
    db.delete(segment)

    new_rev = bump_topology_revision(db)
    db.commit()
    db.refresh(seg_1)
    db.refresh(seg_2)

    return SegmentSplitResponse(
        success=True,
        original_segment_id=str(segment.id),
        segment_1=cable_segment_to_schema(seg_1),
        segment_2=cable_segment_to_schema(seg_2),
        pass_through_continuities_count=pass_through_count,
        cut_terminals_count=cut_terminals_count,
        new_topology_revision=new_rev,
    )


def cable_to_schema(cable: Cable) -> CableRead:
    """Converte modelo Cable para schema CableRead."""
    return CableRead(
        id=str(cable.id),
        code=cable.code,
        model=cable.model,
        fiber_count=cable.fiber_count,
        tube_count=cable.tube_count,
        color_standard=cable.color_standard,
        status=AdministrativeStatus(cable.status),
        notes=cable.notes,
        version=cable.version,
        created_at=cable.created_at,
        updated_at=cable.updated_at,
    )


def tube_to_schema(tube: Tube) -> TubeRead:
    """Converte modelo Tube para schema TubeRead."""
    return TubeRead(
        id=str(tube.id),
        cable_id=str(tube.cable_id),
        number=tube.number,
        color_name=tube.color_name,
        is_logical_group=tube.is_logical_group,
    )


def fiber_to_schema(fiber: Fiber) -> FiberRead:
    """Converte modelo Fiber para schema FiberRead."""
    return FiberRead(
        id=str(fiber.id),
        cable_id=str(fiber.cable_id),
        global_number=fiber.global_number,
        tube_number=fiber.tube.number if fiber.tube else 1,
        tube_position=fiber.tube_position,
        color_name=fiber.color_name,
    )


def fiber_segment_to_schema(fiber_seg: FiberSegment) -> FiberSegmentRead:
    """Converte modelo FiberSegment para schema FiberSegmentRead."""
    return FiberSegmentRead(
        id=str(fiber_seg.id),
        cable_segment_id=str(fiber_seg.cable_segment_id),
        fiber_id=str(fiber_seg.fiber_id),
        fiber_number=fiber_seg.fiber_number,
        terminal_a_id=str(fiber_seg.terminal_a_id),
        terminal_b_id=str(fiber_seg.terminal_b_id),
        occupancy=OccupancyStatus(fiber_seg.occupancy),
    )


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
