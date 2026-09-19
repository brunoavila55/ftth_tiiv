"""Simulação e Teste Real de Recuperação de Desastres (Restore Drill) do FTTH Manager.

Valida os critérios de aceite de B17:
- Criação de cenário completo com topologia física, circuito óptico e anexo real com foto JPEG.
- Backup atômico consistente (DB + Anexos + Manifesto com checksums SHA256).
- Restauração em ambiente 100% isolado (novo banco e novo diretório de storage).
- Validação pós-restauração:
  1. Revisão topológica e integridade referencial preservadas.
  2. Rastreamento óptico fim-a-fim funcional no banco restaurado.
  3. Foto/anexo físico restaurado byte-a-byte idêntico com validação de magic bytes JPEG e SHA256.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.backup_restore import create_backup, restore_backup
from app.core.config import get_settings
from app.modules.attachments.models import Attachment
from app.modules.cables.models import Cable, CableSegment, FiberSegment
from app.modules.connectivity.models import Connection, Terminal
from app.modules.gis.service import bump_topology_revision
from app.modules.inventory.models import Device, Port, Site, Structure
from app.modules.topology.service import trace_optical_path
from app.schemas.topology import TraceRequest

DRILL_SOURCE_DB = "ftth_drill_source"
DRILL_TARGET_DB = "ftth_drill_target"


def get_pg_admin_url() -> str:
    settings = get_settings()
    base_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    # Conecta ao banco 'postgres' padrão para criar/destruir bancos de drill
    parts = base_url.split("/")
    parts[-1] = "postgres"
    return "/".join(parts)


def prepare_isolated_db(db_name: str) -> str:
    admin_url = get_pg_admin_url()
    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {db_name};")
        cur.execute(f"CREATE DATABASE {db_name};")

    target_url = admin_url.rsplit("/", 1)[0] + f"/{db_name}"

    # Instala PostGIS
    with psycopg.connect(target_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Aplica migrações Alembic
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    alembic_cfg.set_main_option(
        "sqlalchemy.url", target_url.replace("postgresql://", "postgresql+psycopg://")
    )
    command.upgrade(alembic_cfg, "head")

    return target_url.replace("postgresql://", "postgresql+psycopg://")


def drop_isolated_db(db_name: str) -> None:
    admin_url = get_pg_admin_url()
    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{db_name}' AND pid <> pg_backend_pid();
                """
        )
        cur.execute(f"DROP DATABASE IF EXISTS {db_name};")


def run_restore_drill() -> bool:
    print("================================================================================")
    print(" [FTTH Manager] B17 — Iniciando Restore Drill em Ambiente Isolado")
    print("================================================================================")

    # 1. Preparar banco de origem isolado
    print(f"1. Criando banco isolado de teste: '{DRILL_SOURCE_DB}'...")
    source_db_url = prepare_isolated_db(DRILL_SOURCE_DB)
    source_storage = Path(tempfile.mkdtemp(prefix="ftth_storage_source_"))

    # Criar imagem JPEG sintética válida com magic bytes padrão \xFF\xD8\xFF\xE0
    sample_jpeg_bytes = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00"
        b"\xff\xd9"
    )
    expected_jpeg_sha = hashlib.sha256(sample_jpeg_bytes).hexdigest()

    engine_source = create_engine(source_db_url)
    term_a_id: str = ""
    cto_id: str = ""
    attachment_id: str = ""

    # 2. Popular banco com topologia óptica + anexo real
    print("2. Populando topologia de teste (POP, CEO, CTO, Circuito Óptico e Foto de Campo)...")
    with Session(engine_source) as db:
        # Site POP
        pop = Site(
            code="POP-DRILL",
            name="POP Drill Teste",
            kind="pop",
            status="installed",
            location=from_shape(Point(-46.6333, -23.5505), srid=4326),
        )
        db.add(pop)
        db.flush()

        # OLT e Porta PON
        olt = Device(
            code="OLT-DRILL",
            kind="olt",
            manufacturer="Huawei",
            model="MA5800",
            status="installed",
            site_id=pop.id,
        )
        db.add(olt)
        db.flush()

        pon_port = Port(
            name="PON 1/1/1",
            role="pon",
            device_id=olt.id,
            connector_type="SC/APC",
        )
        db.add(pon_port)
        db.flush()

        # Postes / Caixas
        pole = Structure(
            site_id=pop.id,
            code="POSTE-DRILL-01",
            kind="pole",
            status="installed",
            location=from_shape(Point(-46.6333, -23.5505), srid=4326),
        )
        cto = Structure(
            site_id=pop.id,
            code="CTO-DRILL-01",
            kind="cto",
            status="installed",
            location=from_shape(Point(-46.6360, -23.5530), srid=4326),
        )
        db.add_all([pole, cto])
        db.flush()
        cto_id = str(cto.id)

        # Cabo, Tubo e Fibra
        from shapely.geometry import LineString

        from app.modules.cables.models import Fiber, Tube

        cable = Cable(
            code="CABO-DRILL",
            model="AS-80-6FO",
            fiber_count=6,
            tube_count=1,
            color_standard="NBR",
            status="installed",
        )
        db.add(cable)
        db.flush()

        tube = Tube(
            cable_id=cable.id,
            number=1,
            color_name="Verde",
        )
        db.add(tube)
        db.flush()

        fiber = Fiber(
            cable_id=cable.id,
            tube_id=tube.id,
            global_number=1,
            tube_position=1,
            color_name="Verde",
        )
        db.add(fiber)
        db.flush()

        # Trecho de Cabo
        seg = CableSegment(
            cable_id=cable.id,
            origin_structure_id=pole.id,
            destination_structure_id=cto.id,
            map_length_m=350.0,
            effective_length_m=350.0,
            length_source="measured",
            status="installed",
            geometry=from_shape(
                LineString([(-46.6333, -23.5505), (-46.6360, -23.5530)]), srid=4326
            ),
        )
        db.add(seg)
        db.flush()

        # Terminais ópticos: Porta PON e Cabo Fibra Pontas A e B
        term_pon = Terminal(
            entity_type="port",
            entity_id=pon_port.id,
            site_id=pop.id,
            kind="port_front",
            label="Porta PON 1/1/1",
            is_occupied=True,
            occupancy="connected",
        )
        term_a = Terminal(
            entity_type="fiber_segment",
            entity_id=seg.id,
            site_id=pop.id,
            kind="fiber_endpoint",
            label="FO #1 Ponta A (POP)",
            is_occupied=True,
            occupancy="connected",
        )
        term_b = Terminal(
            entity_type="fiber_segment",
            entity_id=seg.id,
            structure_id=cto.id,
            kind="fiber_endpoint",
            label="FO #1 Ponta B (CTO)",
            is_occupied=True,
            occupancy="connected",
        )
        db.add_all([term_pon, term_a, term_b])
        db.flush()
        term_a_id = str(term_pon.id)

        # Instanciação da fibra no segmento
        fseg = FiberSegment(
            cable_segment_id=seg.id,
            fiber_id=fiber.id,
            fiber_number=1,
            terminal_a_id=term_a.id,
            terminal_b_id=term_b.id,
            occupancy="connected",
        )
        db.add(fseg)
        db.flush()

        # Conexão interna: Patch cord no POP ligando PON ao Cabo FO #1
        conn = Connection(
            terminal_a_id=term_pon.id,
            terminal_b_id=term_a.id,
            site_id=pop.id,
            connection_type="patchcord",
            loss_db=0.2,
            is_active=True,
        )
        db.add(conn)

        # Salvar arquivo físico da foto no storage
        attachment_filename = f"{uuid.uuid4().hex}.jpg"
        att_subfolder = source_storage / "attachments" / "structures" / cto_id
        att_subfolder.mkdir(parents=True, exist_ok=True)
        photo_file_path = att_subfolder / attachment_filename
        with open(photo_file_path, "wb") as pf:
            pf.write(sample_jpeg_bytes)

        # Registro do Anexo no banco
        att = Attachment(
            entity_type="structure",
            entity_id=cto.id,
            file_name="foto_cto_drill.jpg",
            content_type="image/jpeg",
            file_size_bytes=len(sample_jpeg_bytes),
            storage_path=str(photo_file_path.relative_to(source_storage)),
            checksum_sha256=expected_jpeg_sha,
            caption="Foto de teste do drill",
        )
        db.add(att)
        db.flush()
        attachment_id = str(att.id)

        bump_topology_revision(db)
        db.commit()

    # Validar que a origem funciona antes do backup
    with Session(engine_source) as db:
        trace_req = TraceRequest(start_terminal_id=term_a_id, direction="downstream")
        trace_orig = trace_optical_path(db, trace_req)
        assert len(trace_orig.paths) > 0 and len(trace_orig.paths[0].steps) >= 2, (
            f"Trace na origem com poucos passos: {len(trace_orig.paths)}"
        )
        print(
            f"   [Origem OK] Trace óptico concluído com {len(trace_orig.paths[0].steps)} passos ({trace_orig.status}). Revisão: #{trace_orig.topology_revision}"
        )

    # 3. Executar Backup
    backup_dir = Path(tempfile.mkdtemp(prefix="ftth_backups_drill_"))
    print(f"3. Executando backup consistente para '{backup_dir}'...")
    backup_archive = create_backup(
        target_dir=backup_dir,
        db_url=source_db_url,
        storage_path=source_storage,
    )
    print(f"   Arquivo gerado: {backup_archive.name} ({backup_archive.stat().st_size} bytes)")

    # 4. Preparar banco de destino isolado
    print(f"4. Criando banco isolado de restauração: '{DRILL_TARGET_DB}'...")
    target_db_url = prepare_isolated_db(DRILL_TARGET_DB)
    target_storage = Path(tempfile.mkdtemp(prefix="ftth_storage_target_"))

    # 5. Executar Restauração
    print(f"5. Restaurando backup no ambiente isolado ({DRILL_TARGET_DB})...")
    manifest = restore_backup(
        archive_path=backup_archive,
        target_db_url=target_db_url,
        target_storage_path=target_storage,
        verify_checksums=True,
    )

    # 6. Validação Pós-Restauração
    print("6. Verificando integridade total do ambiente restaurado...")
    engine_target = create_engine(target_db_url)
    with Session(engine_target) as db:
        from sqlalchemy import func

        # A. Checar Topologia e Circuito Óptico
        trace_req = TraceRequest(start_terminal_id=term_a_id, direction="downstream")
        trace_restored = trace_optical_path(db, trace_req)
        assert trace_restored.status == trace_orig.status, (
            f"Status do trace divergiu: {trace_restored.status} != {trace_orig.status}"
        )
        assert len(trace_restored.paths) == len(trace_orig.paths), (
            "Quantidade de caminhos divergiu!"
        )
        assert len(trace_restored.paths[0].steps) == len(trace_orig.paths[0].steps), (
            "Quantidade de passos divergiu!"
        )
        assert trace_restored.topology_revision == manifest.topology_revision, (
            "Revisão topológica diverge!"
        )
        print(
            f"   [TESTE 1 PASS] Trace óptico restaurado idêntico: {len(trace_restored.paths[0].steps)} passos ({trace_restored.status})."
        )

        # B. Checar Anexo e Foto Física
        att_restored = db.get(Attachment, uuid.UUID(attachment_id))
        assert att_restored is not None, "Registro do anexo não encontrado no banco restaurado!"
        assert att_restored.checksum_sha256 == expected_jpeg_sha, "Hash do anexo diverge no banco!"

        restored_file = target_storage / att_restored.storage_path
        assert restored_file.exists(), (
            f"Arquivo físico da foto não existe no disco restaurado: {restored_file}"
        )

        with open(restored_file, "rb") as rf:
            restored_bytes = rf.read()

        assert len(restored_bytes) == len(sample_jpeg_bytes), (
            "Tamanho do arquivo restaurado diverge!"
        )
        assert hashlib.sha256(restored_bytes).hexdigest() == expected_jpeg_sha, (
            "Hash do arquivo físico difere!"
        )
        assert restored_bytes[:3] == b"\xff\xd8\xff", (
            "Magic bytes de JPEG inválidos no arquivo restaurado!"
        )
        print("   [TESTE 2 PASS] Foto restaurada byte-a-byte com validação JPEG e SHA256.")

        # C. Checar Contagem de Entidades
        site_count = db.scalar(select(func.count(Site.id)))
        struct_count = db.scalar(select(func.count(Structure.id)))
        assert site_count == 1 and struct_count == 2, (
            f"Contadores de inventário divergem ({site_count}, {struct_count})!"
        )
        print(
            f"   [TESTE 3 PASS] Inventário intacto ({site_count} site, {struct_count} estruturas)."
        )

    # 7. Limpeza dos Bancos e Pastas Temporárias do Drill
    print("7. Limpando bancos e volumes temporários de teste...")
    drop_isolated_db(DRILL_SOURCE_DB)
    drop_isolated_db(DRILL_TARGET_DB)
    shutil.rmtree(source_storage, ignore_errors=True)
    shutil.rmtree(target_storage, ignore_errors=True)
    shutil.rmtree(backup_dir, ignore_errors=True)

    print("================================================================================")
    print(" RESTORE DRILL B17: SUCESSO ABSOLUTO (PASS 100%)")
    print("================================================================================")
    return True


if __name__ == "__main__":
    success = run_restore_drill()
    sys.exit(0 if success else 1)
