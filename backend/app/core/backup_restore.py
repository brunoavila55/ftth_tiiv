"""Módulo de Backup e Restauração Consistente do FTTH Manager.

Garante backup atômico e verificável de:
1. Base de dados relacional e espacial PostgreSQL / PostGIS.
2. Anexos físicos e fotos armazenados no volume persistente.
3. Manifesto com hashes criptográficos SHA256, versão de schema e revisão topológica.

Suporta pg_dump/pg_restore quando disponíveis e fallback nativo via protocolo binário COPY do
psycopg (snapshot REPEATABLE READ; a restauração desativa triggers só durante a carga e revalida
TODAS as chaves estrangeiras antes do commit).

Segurança (SEC-10 / EST-19):
- manifesto autenticado por HMAC-SHA256 (`BACKUP_SIGNING_KEY`), verificado ANTES de extrair;
- toda extração de tar usa `filter="data"` (sem path traversal/links) e nomes validados;
- nomes de tabela vindos do arquivo passam por regex + allowlist (information_schema) e por
  `psycopg.sql.Identifier` — nunca são interpolados em SQL;
- pacote opcionalmente criptografado com AES-256-GCM (`BACKUP_ENCRYPTION_KEY`), permissão 0600.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Literal, cast
from urllib.parse import urlparse

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.backup_crypto import (
    BackupCryptoError,
    decrypt_file,
    encrypt_file,
    is_encrypted_file,
)
from app.core.config import get_settings
from app.core.storage_backend import StorageBackend, get_storage_backend
from app.db.session import get_session_factory

logger = logging.getLogger("ftth.backup")

EXCLUDED_TABLES = {"spatial_ref_sys", "raster_columns", "raster_overviews"}
TABLE_MEMBER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}\.bin$")
MAX_MANIFEST_BYTES = 1024 * 1024
# Usada só fora de produção quando BACKUP_SIGNING_KEY não está definida (em produção é obrigatória)
DEV_SIGNING_KEY = "ftth-manager-dev-backup-signing-key-not-for-production"


class BackupError(Exception):
    """Falha operacional de backup/restore."""


class BackupIntegrityError(BackupError, ValueError):
    """Pacote adulterado, com assinatura inválida, conteúdo malicioso ou dado inconsistente."""


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
    signature: str = ""  # HMAC-SHA256 do manifesto (sem este campo) com BACKUP_SIGNING_KEY


def get_signing_key() -> str:
    settings = get_settings()
    if settings.BACKUP_SIGNING_KEY:
        return settings.BACKUP_SIGNING_KEY
    if settings.is_production:
        raise BackupError("BACKUP_SIGNING_KEY não configurada (obrigatória em produção).")
    logger.warning(
        "BACKUP_SIGNING_KEY ausente: usando chave de desenvolvimento (não use em produção)."
    )
    return DEV_SIGNING_KEY


def sign_manifest(manifest: dict[str, object], key: str) -> str:
    """HMAC-SHA256 do manifesto canônico (JSON ordenado, sem o campo `signature`)."""
    payload = {k: v for k, v in manifest.items() if k != "signature"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def read_verified_manifest(archive_path: Path) -> BackupManifest:
    """Lê `manifest.json` SEM extrair nada e confere a assinatura antes de qualquer outra ação."""
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            candidates = [m for m in tar.getmembers() if m.name == "manifest.json" and m.isfile()]
            if len(candidates) != 1 or candidates[0].size > MAX_MANIFEST_BYTES:
                raise BackupIntegrityError("Backup inválido: manifest.json ausente ou anômalo.")
            handle = tar.extractfile(candidates[0])
            manifest_dict = json.loads(handle.read().decode("utf-8")) if handle else {}
    except (tarfile.TarError, OSError, ValueError, UnicodeDecodeError) as err:
        if isinstance(err, BackupIntegrityError):
            raise
        raise BackupIntegrityError(f"Backup ilegível ou corrompido: {err}") from err

    signature = str(manifest_dict.get("signature") or "")
    expected = sign_manifest(manifest_dict, get_signing_key())
    if not signature or not hmac.compare_digest(signature, expected):
        raise BackupIntegrityError(
            "Assinatura do manifesto inválida ou ausente: o backup foi adulterado, "
            "é de outra instalação ou foi gerado sem assinatura."
        )
    try:
        return BackupManifest(**manifest_dict)
    except TypeError as err:
        raise BackupIntegrityError(f"Manifesto com campos inesperados: {err}") from err


def safe_extract(
    archive: Path, destination: Path, mode: Literal["r:*", "r:gz", "r:"] = "r:*"
) -> None:
    """Extrai um tar com o filtro seguro `data` (bloqueia `..`, caminhos absolutos, links e devices)."""
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, mode) as tar:
            tar.extractall(path=destination, filter="data")
    except (tarfile.FilterError, tarfile.TarError, OSError) as err:
        raise BackupIntegrityError(
            f"Conteúdo do pacote recusado (extração insegura): {err}"
        ) from err


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


def _raw_url(db_url: str) -> str:
    return db_url.replace("postgresql+psycopg://", "postgresql://")


def dump_database_psycopg_binary(
    db_url: str,
    output_dir: Path,
    on_table_dumped: Callable[[str], None] | None = None,
) -> Path:
    """Exporta as tabelas em COPY binário dentro de UM snapshot (REPEATABLE READ, somente leitura).

    Todas as tabelas refletem o mesmo instante: escritas concorrentes durante o dump não geram
    linhas-filhas sem o pai. `on_table_dumped` é um gancho para testes.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(_raw_url(db_url)) as conn:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        with conn.cursor() as cur:
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
                query = sql.SQL("COPY {} TO STDOUT (FORMAT binary)").format(sql.Identifier(t))
                with open(t_file, "wb") as f, cur.copy(query) as copy:
                    for chunk in copy:
                        f.write(chunk)
                dump_files.append((t, t_file))
                if on_table_dumped is not None:
                    on_table_dumped(t)

    # Compacta em um único arquivo de banco
    final_dump = output_dir / "database.dump"
    with tarfile.open(final_dump, "w") as tar:
        for t, f_path in dump_files:
            tar.add(f_path, arcname=f"{t}.bin")
            f_path.unlink()

    return final_dump


def _verify_foreign_keys(cur: psycopg.Cursor) -> None:
    """Falha se alguma chave estrangeira do schema public estiver violada (linha filha sem pai)."""
    cur.execute(
        """
        SELECT c.conname,
               (SELECT relname FROM pg_class WHERE oid = c.conrelid),
               (SELECT relname FROM pg_class WHERE oid = c.confrelid),
               (SELECT array_agg(a.attname::text ORDER BY k.ord)
                  FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum),
               (SELECT array_agg(a.attname::text ORDER BY k.ord)
                  FROM unnest(c.confkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum)
        FROM pg_constraint c
        WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
        """
    )
    constraints = cur.fetchall()
    violated: list[str] = []
    for conname, child, parent, child_cols, parent_cols in constraints:
        not_null = sql.SQL(" AND ").join(
            sql.SQL("c.{} IS NOT NULL").format(sql.Identifier(col)) for col in child_cols
        )
        match = sql.SQL(" AND ").join(
            sql.SQL("p.{} = c.{}").format(sql.Identifier(pc), sql.Identifier(cc))
            for cc, pc in zip(child_cols, parent_cols, strict=True)
        )
        query = sql.SQL(
            "SELECT 1 FROM {child} c WHERE {not_null} "
            "AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE {match}) LIMIT 1"
        ).format(
            child=sql.Identifier(child),
            parent=sql.Identifier(parent),
            not_null=not_null,
            match=match,
        )
        cur.execute(query)
        if cur.fetchone() is not None:
            violated.append(f"{child}.{conname}")
    if violated:
        raise BackupIntegrityError(
            "Restauração recusada: violação de integridade referencial em "
            + ", ".join(sorted(violated))
        )


def restore_database_psycopg_binary(db_url: str, dump_path: Path) -> None:
    """Restaura as tabelas com COPY FROM binário, de forma atômica e validada.

    1. valida os nomes dos membros do dump (regex) — antes de abrir qualquer conexão;
    2. confere cada tabela contra a allowlist do banco (information_schema);
    3. carrega tudo numa transação com triggers desativados, revalida as chaves estrangeiras e só
       então faz commit (qualquer falha reverte tudo).
    """
    with tempfile.TemporaryDirectory(prefix="ftth_restore_db_") as tmp:
        extract_dir = Path(tmp)
        try:
            with tarfile.open(dump_path, "r") as tar:
                names = [m.name for m in tar.getmembers()]
        except (tarfile.TarError, OSError) as err:
            raise BackupIntegrityError(f"Dump do banco ilegível: {err}") from err
        invalid = [n for n in names if not TABLE_MEMBER_PATTERN.fullmatch(n)]
        if invalid:
            raise BackupIntegrityError(
                f"Dump recusado: nome(s) de tabela inválido(s) no arquivo: {invalid[:3]!r}"
            )
        safe_extract(dump_path, extract_dir, "r:")

        with psycopg.connect(_raw_url(db_url), autocommit=False) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
            allowed = {r[0] for r in cur.fetchall()} - EXCLUDED_TABLES
            bin_files = sorted(extract_dir.glob("*.bin"))
            unknown = [f.stem for f in bin_files if f.stem not in allowed]
            if unknown:
                raise BackupIntegrityError(
                    f"Dump recusado: tabela(s) inexistente(s) no schema do destino: {unknown[:3]!r}"
                )

            # Desativa temporariamente triggers/FKs para a carga em lote
            cur.execute("SET session_replication_role = 'replica';")
            for f in bin_files:
                cur.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(sql.Identifier(f.stem)))
            for f in bin_files:
                copy_sql = sql.SQL("COPY {} FROM STDIN (FORMAT binary)").format(
                    sql.Identifier(f.stem)
                )
                with open(f, "rb") as bf, cur.copy(copy_sql) as copy:
                    while chunk := bf.read(65536):
                        copy.write(chunk)

            cur.execute("SET session_replication_role = 'origin';")
            _verify_foreign_keys(cur)  # falha → o `with` faz rollback de toda a carga
            conn.commit()


def _tar_attachments_from_local(storage_path: Path, attachments_tar: Path) -> int:
    """Anexos em volume local (padrão): mesmo comportamento de sempre."""
    files_count = 0
    with tarfile.open(attachments_tar, "w:gz") as tar:
        if storage_path.exists():
            for root, _, files in os.walk(storage_path):
                for file in files:
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(storage_path)
                    tar.add(full_p, arcname=str(rel_p))
                    files_count += 1
    return files_count


def _tar_attachments_from_bucket(backend: StorageBackend, attachments_tar: Path) -> int:
    """Anexos em S3/MinIO (item 4 do épico, ADR 0007): baixa todo o bucket para o pacote de backup —
    sem isso, quem usa `STORAGE_BACKEND=s3` depende só da durabilidade própria do bucket."""
    files_count = 0
    with tarfile.open(attachments_tar, "w:gz") as tar:
        for entry in backend.list(""):
            with contextlib.closing(backend.open_read(entry.key)) as fh:
                info = tarfile.TarInfo(name=entry.key)
                info.size = entry.size_bytes
                info.mtime = int(entry.mtime)
                tar.addfile(info, fileobj=fh)
            files_count += 1
    return files_count


def _reject_unsafe_member_name(name: str) -> None:
    if name.startswith(("/", "\\")) or ".." in Path(name).parts:
        raise BackupIntegrityError(f"Backup recusado: nome de anexo inseguro no pacote: {name!r}")


def _restore_attachments_to_bucket(backend: StorageBackend, attachments_tar: Path) -> None:
    """Restaura anexos para S3/MinIO. `safe_extract` não se aplica (não há filesystem de destino);
    cada nome de membro é validado individualmente antes de gravar no bucket."""
    with tarfile.open(attachments_tar, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            _reject_unsafe_member_name(member.name)
            fh = tar.extractfile(member)
            if fh is None:
                continue
            with backend.save_stream(member.name) as out:
                out_bytes = cast("IO[bytes]", out)
                while chunk := fh.read(65536):
                    out_bytes.write(chunk)


def create_backup(
    target_dir: Path | str | None = None,
    db_url: str | None = None,
    storage_path: Path | str | None = None,
) -> Path:
    """Executa o procedimento completo de backup atômico de DB e Anexos.

    Anexos: se `storage_path` for informado (explicitamente, ou por `STORAGE_BACKEND=local`), lê o
    volume local; se `STORAGE_BACKEND=s3` e nenhum `storage_path` for informado, baixa o bucket
    inteiro do S3/MinIO configurado (`get_storage_backend()`).
    """
    settings = get_settings()
    db_url = db_url or settings.DATABASE_URL
    use_bucket = storage_path is None and settings.STORAGE_BACKEND == "s3"
    storage_path_resolved = Path(storage_path or settings.STORAGE_PATH)
    signing_key = get_signing_key()  # falha cedo (produção sem chave)

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
            parsed = urlparse(_raw_url(db_url))
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
                "-Fc",  # snapshot único e consistente
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
        if use_bucket:
            files_count = _tar_attachments_from_bucket(get_storage_backend(), attachments_tar)
        else:
            files_count = _tar_attachments_from_local(storage_path_resolved, attachments_tar)

        att_sha256 = calculate_sha256(attachments_tar)
        att_size = attachments_tar.stat().st_size

        # 4. Criar Manifesto autenticado (HMAC-SHA256)
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
        manifest_dict = asdict(manifest)
        manifest_dict["signature"] = sign_manifest(manifest_dict, signing_key)

        manifest_file = tmp_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_dict, f, indent=2)

        # 5. Compactar Pacote Final
        with tarfile.open(final_archive_path, "w:gz") as tar:
            tar.add(manifest_file, arcname="manifest.json")
            tar.add(db_dump_file, arcname="database.dump")
            tar.add(attachments_tar, arcname="attachments.tar.gz")

        # 6. Criptografia opcional do pacote (AES-256-GCM); o texto claro é removido
        encryption_key = settings.BACKUP_ENCRYPTION_KEY
        if encryption_key:
            encrypted_path = final_archive_path.with_name(final_archive_path.name + ".enc")
            encrypt_file(final_archive_path, encrypted_path, encryption_key)
            final_archive_path.unlink()
            final_archive_path = encrypted_path
        else:
            logger.warning(
                "Backup SEM criptografia (BACKUP_ENCRYPTION_KEY ausente): proteja o arquivo "
                "com controles de acesso/criptografia de disco."
            )
        final_archive_path.chmod(0o600)  # só o dono lê

        manifest.total_archive_size_bytes = final_archive_path.stat().st_size

    logger.info(
        f"Backup concluído com sucesso: {final_archive_path.name} "
        f"({manifest.total_archive_size_bytes / 1024:.1f} KB, rev #{topo_rev}, "
        f"{'criptografado' if encryption_key else 'sem criptografia'})"
    )
    return final_archive_path


# Entradas do sumário do pg_restore que pertencem à extensão PostGIS, não aos dados do sistema.
_EXTENSION_ENTRY = re.compile(
    r"^\d+;\s+\d+\s+\d+\s+(?:EXTENSION\b|COMMENT\s+-\s+EXTENSION\b|TABLE DATA public spatial_ref_sys\b)"
)


def _write_restore_list(dump_file: Path, list_file: Path, env: dict[str, str]) -> Path:
    """Sumário do dump sem a extensão PostGIS, para `pg_restore -L`.

    `--clean` derrubaria e recriaria a extensão: os OIDs de tipos e classes de operadores mudam e as
    conexões já abertas (pool da API e do worker) passam a falhar em `ST_Intersects` até reiniciar.
    A extensão já existe no destino (migração 0001); só o schema e os dados do sistema são restaurados.
    """
    listing = subprocess.run(
        ["pg_restore", "-l", str(dump_file)], env=env, capture_output=True, text=True, check=True
    )
    kept = [line for line in listing.stdout.splitlines() if not _EXTENSION_ENTRY.match(line)]
    list_file.write_text("\n".join(kept) + "\n")
    return list_file


def restore_backup(
    archive_path: Path | str,
    target_db_url: str | None = None,
    target_storage_path: Path | str | None = None,
    verify_checksums: bool = True,
) -> BackupManifest:
    """Restaura banco e anexos a partir de um pacote autenticado e verificado.

    Ordem: (0) decifra, se criptografado; (1) verifica a assinatura do manifesto ANTES de extrair;
    (2) extrai com filtro seguro; (3) confere os checksums; (4) restaura banco e anexos.
    """
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Arquivo de backup não encontrado: {archive_path}")

    settings = get_settings()
    target_db_url = target_db_url or settings.DATABASE_URL
    use_bucket = target_storage_path is None and settings.STORAGE_BACKEND == "s3"
    target_storage_path_resolved = Path(target_storage_path or settings.STORAGE_PATH)

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # 0. Pacote criptografado: exige a chave e autentica cada bloco (GCM)
        working_archive = archive_path
        if is_encrypted_file(archive_path):
            if not settings.BACKUP_ENCRYPTION_KEY:
                raise BackupIntegrityError(
                    "Backup criptografado: defina BACKUP_ENCRYPTION_KEY para restaurar."
                )
            working_archive = tmp_dir / "decrypted.tar.gz"
            try:
                decrypt_file(archive_path, working_archive, settings.BACKUP_ENCRYPTION_KEY)
            except BackupCryptoError as err:
                raise BackupIntegrityError(str(err)) from err

        # 1. Assinatura do manifesto — antes de extrair QUALQUER arquivo
        manifest = read_verified_manifest(working_archive)

        # 2. Extração segura
        extract_dir = tmp_dir / "pkg"
        safe_extract(working_archive, extract_dir, "r:gz")

        db_dump_file = extract_dir / "database.dump"
        attachments_tar = extract_dir / "attachments.tar.gz"
        if not db_dump_file.exists():
            raise BackupIntegrityError("Arquivo de backup inválido: database.dump ausente.")

        # 3. Verificação Criptográfica de Integridade
        if verify_checksums:
            calc_db_sha = calculate_sha256(db_dump_file)
            if calc_db_sha != manifest.database_checksum_sha256:
                raise BackupIntegrityError(
                    f"Integridade corrompida no dump do banco! "
                    f"Esperado: {manifest.database_checksum_sha256}, Obtido: {calc_db_sha}"
                )

            if attachments_tar.exists():
                calc_att_sha = calculate_sha256(attachments_tar)
                if calc_att_sha != manifest.attachments_checksum_sha256:
                    raise BackupIntegrityError(
                        f"Integridade corrompida nos anexos! "
                        f"Esperado: {manifest.attachments_checksum_sha256}, Obtido: {calc_att_sha}"
                    )

        # 4a. Anexos primeiro (extração validada): se forem recusados, o banco nem é tocado
        if attachments_tar.exists() and manifest.attachments_count > 0:
            if use_bucket:
                _restore_attachments_to_bucket(get_storage_backend(), attachments_tar)
            else:
                safe_extract(attachments_tar, target_storage_path_resolved, "r:gz")

        # 4b. Restauração do Banco de Dados
        has_pg_restore = shutil.which("pg_restore") is not None
        if manifest.database_format == "pg_dump" and has_pg_restore:
            parsed = urlparse(_raw_url(target_db_url))
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password
            restore_list = _write_restore_list(db_dump_file, tmp_dir / "restore.list", env)
            with psycopg.connect(_raw_url(target_db_url), autocommit=True) as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")  # destino vazio (DR)
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
                "-L",
                str(restore_list),
                str(db_dump_file),
            ]
            res = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if res.returncode != 0 and "errors ignored on restore" not in res.stderr.lower():
                logger.warning(f"pg_restore avisou: {res.stderr}")
        else:
            restore_database_psycopg_binary(target_db_url, db_dump_file)

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
        [*bdir.glob("ftth_backup_*.tar.gz"), *bdir.glob("ftth_backup_*.tar.gz.enc")],
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
