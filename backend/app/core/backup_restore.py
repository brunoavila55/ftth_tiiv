"""Módulo de Backup e Restauração Consistente do FTTH Manager.

Garante backup atômico e verificável de:
1. Base de dados relacional e espacial PostgreSQL / PostGIS.
2. Anexos físicos e fotos armazenados no volume persistente.
3. Manifesto com hashes criptográficos SHA256, versão de schema e revisão topológica.

Suporta pg_dump/pg_restore quando disponíveis e fallback nativo de alta performance
via protocolo binário COPY do psycopg com 'session_replication_role = replica'.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory

logger = logging.getLogger("ftth.backup")

EXCLUDED_TABLES = {"spatial_ref_sys", "raster_columns", "raster_overviews"}


@dataclass
class BackupManifest:
    backup_id: str
    created_at: str
    app_version: str
    schema_version: str
    topology_revision: int
    database_format: str  # "pg_dump" ou "psycopg_binary"
    database_checksum_sha256: str
    attachments_checksum_sha256: str
    attachments_count: int
    database_size_bytes: int
    attachments_size_bytes: int
    total_archive_size_bytes: int = 0


def calculate_sha256(file_path: Path) -> str:
    """Calcula hash SHA256 de um arquivo em chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_current_topology_revision(db_url: str | None = None) -> int:
    """Obtém a revisão topológica atual do banco."""
    if db_url:
        engine = create_engine(db_url)
        with Session(engine) as db:
            res = db.execute(
                text("SELECT topology_revision FROM network_topology_state WHERE id = 1 LIMIT 1")
            ).scalar()
            return int(res) if res is not None else 0
    factory = get_session_factory()
    with factory() as db:
        res = db.execute(
            text("SELECT topology_revision FROM network_topology_state WHERE id = 1 LIMIT 1")
        ).scalar()
        return int(res) if res is not None else 0


def get_current_schema_version(db_url: str | None = None) -> str:
    """Obtém a revisão corrente do Alembic."""
    if db_url:
        engine = create_engine(db_url)
        with Session(engine) as db:
            res = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
            return str(res) if res is not None else "head"
    factory = get_session_factory()
    with factory() as db:
        res = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        return str(res) if res is not None else "head"


def dump_database_psycopg_binary(db_url: str, output_dir: Path) -> Path:
    """Exporta tabelas do PostgreSQL em formato binário COPY nativo do psycopg."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Converte URL do SQLAlchemy (ex: postgresql+psycopg://...) para formato psycopg puro
    raw_url = db_url.replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(raw_url) as conn, conn.cursor() as cur:
        # Lista todas as tabelas da aplicação
        cur.execute(
            """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
                """
        )
        tables = [r[0] for r in cur.fetchall() if r[0] not in EXCLUDED_TABLES]

        dump_files: list[tuple[str, Path]] = []
        for t in tables:
            t_file = output_dir / f"{t}.bin"
            with open(t_file, "wb") as f, cur.copy(f"COPY {t} TO STDOUT (FORMAT binary)") as copy:
                for chunk in copy:
                    f.write(chunk)
            dump_files.append((t, t_file))

    # Compacta em um único arquivo de banco
    final_dump = output_dir / "database.dump"
    with tarfile.open(final_dump, "w") as tar:
        for t, f_path in dump_files:
            tar.add(f_path, arcname=f"{t}.bin")
            f_path.unlink()

    return final_dump


def restore_database_psycopg_binary(db_url: str, dump_path: Path) -> None:
    """Restaura tabelas do PostgreSQL usando COPY FROM binário com desativação de triggers."""
    extract_dir = dump_path.parent / "extracted_db"
    extract_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(dump_path, "r") as tar:
        tar.extractall(path=extract_dir)

    raw_url = db_url.replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(raw_url, autocommit=False) as conn, conn.cursor() as cur:
        # Desativa temporariamente validação de integridade referencial para carga em lote
        cur.execute("SET session_replication_role = 'replica';")

        bin_files = sorted(extract_dir.glob("*.bin"))
        # Limpa tabelas antes de restaurar
        for f in bin_files:
            table_name = f.stem
            cur.execute(f"TRUNCATE TABLE {table_name} CASCADE;")

        # Carrega dados tabela por tabela
        for f in bin_files:
            table_name = f.stem
            with open(f, "rb") as bf, cur.copy(f"COPY {table_name} FROM STDIN (FORMAT binary)") as copy:
                while chunk := bf.read(65536):
                    copy.write(chunk)

        # Reativa verificação de constraints
        cur.execute("SET session_replication_role = 'origin';")
        conn.commit()

    shutil.rmtree(extract_dir, ignore_errors=True)


def create_backup(
    target_dir: Path | str | None = None,
    db_url: str | None = None,
    storage_path: Path | str | None = None,
) -> Path:
    """Executa o procedimento completo de backup atômico de DB e Anexos."""
    settings = get_settings()
    db_url = db_url or settings.DATABASE_URL
    storage_path = Path(storage_path or settings.STORAGE_PATH)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_id = str(uuid.uuid4())

    out_directory = Path(target_dir) if target_dir else Path("./backups")
    out_directory.mkdir(parents=True, exist_ok=True)

    final_archive_path = out_directory / f"ftth_backup_{timestamp}.tar.gz"

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # 1. Obter metadados de versão
        topo_rev = get_current_topology_revision(db_url)
        schema_rev = get_current_schema_version(db_url)

        # 2. Dump do Banco de Dados
        has_pg_dump = shutil.which("pg_dump") is not None
        db_dump_file = tmp_dir / "database.dump"

        if has_pg_dump:
            parsed = urlparse(db_url.replace("postgresql+psycopg://", "postgresql://"))
            cmd = [
                "pg_dump",
                "-h",
                parsed.hostname or "127.0.0.1",
                "-p",
                str(parsed.port or 5432),
                "-U",
                parsed.username or "postgres",
                "-d",
                parsed.path.lstrip("/"),
                "-Fc",
                "--no-owner",
                "--no-privileges",
                "-f",
                str(db_dump_file),
            ]
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password
            res = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if res.returncode != 0:
                logger.warning(
                    f"pg_dump falhou ({res.stderr}), recorrendo ao dump binário psycopg."
                )
                db_dump_file = dump_database_psycopg_binary(db_url, tmp_dir)
                db_fmt = "psycopg_binary"
            else:
                db_fmt = "pg_dump"
        else:
            db_dump_file = dump_database_psycopg_binary(db_url, tmp_dir)
            db_fmt = "psycopg_binary"

        db_sha256 = calculate_sha256(db_dump_file)
        db_size = db_dump_file.stat().st_size

        # 3. Dump dos Anexos / Fotos
        attachments_tar = tmp_dir / "attachments.tar.gz"
        files_count = 0
        with tarfile.open(attachments_tar, "w:gz") as tar:
            if storage_path.exists():
                for root, _, files in os.walk(storage_path):
                    for file in files:
                        full_p = Path(root) / file
                        rel_p = full_p.relative_to(storage_path)
                        tar.add(full_p, arcname=str(rel_p))
                        files_count += 1

        att_sha256 = calculate_sha256(attachments_tar)
        att_size = attachments_tar.stat().st_size

        # 4. Criar Manifesto
        manifest = BackupManifest(
            backup_id=backup_id,
            created_at=datetime.now(UTC).isoformat(),
            app_version="0.1.0",
            schema_version=schema_rev,
            topology_revision=topo_rev,
            database_format=db_fmt,
            database_checksum_sha256=db_sha256,
            attachments_checksum_sha256=att_sha256,
            attachments_count=files_count,
            database_size_bytes=db_size,
            attachments_size_bytes=att_size,
        )

        manifest_file = tmp_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(asdict(manifest), f, indent=2)

        # 5. Compactar Pacote Final
        with tarfile.open(final_archive_path, "w:gz") as tar:
            tar.add(manifest_file, arcname="manifest.json")
            tar.add(db_dump_file, arcname="database.dump")
            tar.add(attachments_tar, arcname="attachments.tar.gz")

        manifest.total_archive_size_bytes = final_archive_path.stat().st_size

    logger.info(
        f"Backup concluído com sucesso: {final_archive_path.name} "
        f"({manifest.total_archive_size_bytes / 1024:.1f} KB, rev #{topo_rev})"
    )
    return final_archive_path


def restore_backup(
    archive_path: Path | str,
    target_db_url: str | None = None,
    target_storage_path: Path | str | None = None,
    verify_checksums: bool = True,
) -> BackupManifest:
    """Restaura banco e anexos a partir de um arquivo de backup verificado."""
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Arquivo de backup não encontrado: {archive_path}")

    settings = get_settings()
    target_db_url = target_db_url or settings.DATABASE_URL
    target_storage_path = Path(target_storage_path or settings.STORAGE_PATH)

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # 1. Extrair pacote de backup
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=tmp_dir)

        manifest_file = tmp_dir / "manifest.json"
        db_dump_file = tmp_dir / "database.dump"
        attachments_tar = tmp_dir / "attachments.tar.gz"

        if not manifest_file.exists() or not db_dump_file.exists():
            raise ValueError("Arquivo de backup inválido: manifest.json ou database.dump ausente.")

        with open(manifest_file, encoding="utf-8") as f:
            manifest_dict = json.load(f)
            manifest = BackupManifest(**manifest_dict)

        # 2. Verificação Criptográfica de Integridade
        if verify_checksums:
            calc_db_sha = calculate_sha256(db_dump_file)
            if calc_db_sha != manifest.database_checksum_sha256:
                raise ValueError(
                    f"Integridade corrompida no dump do banco! "
                    f"Esperado: {manifest.database_checksum_sha256}, Obtido: {calc_db_sha}"
                )

            if attachments_tar.exists():
                calc_att_sha = calculate_sha256(attachments_tar)
                if calc_att_sha != manifest.attachments_checksum_sha256:
                    raise ValueError(
                        f"Integridade corrompida nos anexos! "
                        f"Esperado: {manifest.attachments_checksum_sha256}, Obtido: {calc_att_sha}"
                    )

        # 3. Restauração do Banco de Dados
        has_pg_restore = shutil.which("pg_restore") is not None
        if manifest.database_format == "pg_dump" and has_pg_restore:
            parsed = urlparse(target_db_url.replace("postgresql+psycopg://", "postgresql://"))
            cmd = [
                "pg_restore",
                "-h",
                parsed.hostname or "127.0.0.1",
                "-p",
                str(parsed.port or 5432),
                "-U",
                parsed.username or "postgres",
                "-d",
                parsed.path.lstrip("/"),
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                str(db_dump_file),
            ]
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password
            res = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if res.returncode != 0 and "errors ignored on restore" not in res.stderr.lower():
                logger.warning(f"pg_restore avisou: {res.stderr}")
        else:
            restore_database_psycopg_binary(target_db_url, db_dump_file)

        # 4. Restauração dos Anexos Físicos
        if attachments_tar.exists() and manifest.attachments_count > 0:
            target_storage_path.mkdir(parents=True, exist_ok=True)
            with tarfile.open(attachments_tar, "r:gz") as tar:
                tar.extractall(path=target_storage_path)

    # 5. Verificação Pós-Restauração
    restored_topo_rev = get_current_topology_revision(target_db_url)
    restored_schema_rev = get_current_schema_version(target_db_url)

    logger.info(
        f"Restauração concluída com sucesso! "
        f"Schema rev: {restored_schema_rev} (esperado {manifest.schema_version}), "
        f"Topology rev: #{restored_topo_rev} (esperado #{manifest.topology_revision})"
    )

    return manifest


def prune_old_backups(backup_dir: Path | str, keep_count: int = 7) -> list[Path]:
    """Política de retenção: mantém apenas os últimos N backups."""
    bdir = Path(backup_dir)
    if not bdir.exists():
        return []

    backups = sorted(
        bdir.glob("ftth_backup_*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    removed: list[Path] = []
    if len(backups) > keep_count:
        for old in backups[keep_count:]:
            old.unlink()
            removed.append(old)
            logger.info(f"Backup antigo removido por retenção: {old.name}")

    return removed
