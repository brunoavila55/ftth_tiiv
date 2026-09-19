"""R19 (SEC-10 / EST-19): backup/restore seguros — tar traversal, SQL por nome de arquivo,
manifesto autenticado, snapshot consistente sob escrita concorrente e criptografia do pacote."""

import io
import json
import os
import subprocess
import sys
import tarfile
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core import backup_restore
from app.core.backup_restore import (
    BackupIntegrityError,
    create_backup,
    dump_database_psycopg_binary,
    restore_backup,
    sign_manifest,
)
from app.core.config import get_settings
from app.modules.inventory.models import Site, Structure

ENC_KEY = "0f" * 32  # 64 hex = 32 bytes
SIGNING_KEY = "backup-signing-key-de-teste-com-mais-de-trinta-e-dois-caracteres"
BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def backup_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKUP_SIGNING_KEY", SIGNING_KEY)
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    get_settings.cache_clear()


def source_db_url() -> str:
    return os.environ["DATABASE_URL"]


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    root = tmp_path / "storage"
    (root / "attachments").mkdir(parents=True)
    (root / "attachments" / "foto.txt").write_text("conteudo do anexo")
    return root


def read_tar_bytes(archive: Path) -> dict[str, bytes]:
    with tarfile.open(archive, "r:gz") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}  # type: ignore[union-attr]


def write_archive(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def resign(members: dict[str, bytes]) -> dict[str, bytes]:
    """Reassina o manifesto de um pacote reconstruído (simula quem possui a chave de assinatura)."""
    manifest = json.loads(members["manifest.json"])
    manifest.pop("signature", None)
    import hashlib

    manifest["database_checksum_sha256"] = hashlib.sha256(members["database.dump"]).hexdigest()
    manifest["attachments_checksum_sha256"] = hashlib.sha256(
        members["attachments.tar.gz"]
    ).hexdigest()
    manifest["signature"] = sign_manifest(manifest, SIGNING_KEY)
    return {**members, "manifest.json": json.dumps(manifest).encode()}


def make_backup(tmp_path: Path, storage: Path) -> Path:
    return create_backup(target_dir=tmp_path / "bkp", storage_path=storage)


# ---------------------------------------------------------------------------------------------
# Manifesto autenticado (verificado ANTES de extrair)
# ---------------------------------------------------------------------------------------------


def test_backup_manifest_is_signed_and_archive_is_private(tmp_path: Path, storage: Path) -> None:
    archive = make_backup(tmp_path, storage)
    manifest = json.loads(read_tar_bytes(archive)["manifest.json"])
    assert manifest["signature"] and len(manifest["signature"]) == 64  # HMAC-SHA256 hex
    assert (archive.stat().st_mode & 0o777) == 0o600  # só o dono lê


def test_tampered_manifest_is_rejected_before_any_extraction(
    tmp_path: Path, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_backup(tmp_path, storage)
    members = read_tar_bytes(archive)
    manifest = json.loads(members["manifest.json"])
    manifest["topology_revision"] = 999_999  # adulterado, assinatura antiga
    members["manifest.json"] = json.dumps(manifest).encode()
    write_archive(archive, members)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("nada pode ser extraído antes de validar a assinatura")

    monkeypatch.setattr(tarfile.TarFile, "extractall", forbidden)
    monkeypatch.setattr(tarfile.TarFile, "extract", forbidden)
    with pytest.raises(BackupIntegrityError, match="assinatura"):
        restore_backup(archive, target_storage_path=tmp_path / "restore")
    assert not (tmp_path / "restore").exists()


def test_manifest_signed_with_another_key_or_missing_signature_is_rejected(
    tmp_path: Path, storage: Path
) -> None:
    archive = make_backup(tmp_path, storage)
    members = read_tar_bytes(archive)
    manifest = json.loads(members["manifest.json"])

    forged = dict(manifest)
    forged["signature"] = sign_manifest(
        {k: v for k, v in manifest.items() if k != "signature"}, "outra-chave-" * 4
    )
    write_archive(archive, {**members, "manifest.json": json.dumps(forged).encode()})
    with pytest.raises(BackupIntegrityError, match="assinatura"):
        restore_backup(archive, target_storage_path=tmp_path / "r1")

    unsigned = {k: v for k, v in manifest.items() if k != "signature"}
    write_archive(archive, {**members, "manifest.json": json.dumps(unsigned).encode()})
    with pytest.raises(BackupIntegrityError, match="assinatura"):
        restore_backup(archive, target_storage_path=tmp_path / "r2")


# ---------------------------------------------------------------------------------------------
# Path traversal
# ---------------------------------------------------------------------------------------------


def test_outer_archive_with_path_traversal_member_is_refused(tmp_path: Path, storage: Path) -> None:
    archive = make_backup(tmp_path, storage)
    members = resign(read_tar_bytes(archive))
    members["../evil-outer.txt"] = b"pwn"
    write_archive(archive, members)
    escape = Path(tempfile_dir()) / "evil-outer.txt"
    escape.unlink(missing_ok=True)

    with pytest.raises(BackupIntegrityError):
        restore_backup(archive, target_storage_path=tmp_path / "restore")
    assert not escape.exists()


def tempfile_dir() -> str:
    import tempfile

    return str(Path(tempfile.gettempdir()))


def test_attachments_archive_with_path_traversal_is_refused(tmp_path: Path, storage: Path) -> None:
    archive = make_backup(tmp_path, storage)
    members = read_tar_bytes(archive)
    att = io.BytesIO()
    with tarfile.open(fileobj=att, mode="w:gz") as tar:
        info = tarfile.TarInfo("../../escape-attachments.txt")
        info.size = 3
        tar.addfile(info, io.BytesIO(b"pwn"))
    members["attachments.tar.gz"] = att.getvalue()
    manifest = json.loads(members["manifest.json"])
    manifest["attachments_count"] = 1
    members["manifest.json"] = json.dumps(manifest).encode()
    write_archive(archive, resign(members))

    restore_root = tmp_path / "a" / "b" / "restore"
    with pytest.raises(BackupIntegrityError):
        restore_backup(archive, target_storage_path=restore_root)
    assert not (tmp_path / "a" / "escape-attachments.txt").exists()
    assert not (tmp_path / "escape-attachments.txt").exists()


# ---------------------------------------------------------------------------------------------
# SQL: nome de tabela vindo do arquivo
# ---------------------------------------------------------------------------------------------


def dump_with_member(name: str, payload: bytes = b"") -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as tar:
        info = tarfile.TarInfo(name)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    return out.getvalue()


def test_malicious_table_name_is_refused_before_any_sql(
    tmp_path: Path, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = make_backup(tmp_path, storage)
    members = read_tar_bytes(archive)
    members["database.dump"] = dump_with_member("a;drop table users.bin")
    manifest = json.loads(members["manifest.json"])
    manifest["database_format"] = "psycopg_binary"
    members["manifest.json"] = json.dumps(manifest).encode()
    write_archive(archive, resign(members))

    def no_sql(*args: object, **kwargs: object) -> None:
        raise AssertionError("nenhuma conexão/SQL antes de validar os nomes")

    monkeypatch.setattr(psycopg, "connect", no_sql)
    with pytest.raises(BackupIntegrityError, match="tabela"):
        restore_backup(archive, target_storage_path=tmp_path / "restore")


def test_unknown_table_name_is_refused_by_allowlist_and_nothing_is_truncated(
    tmp_path: Path, db_session: Session, storage: Path
) -> None:
    from tests.conftest import create_test_user

    create_test_user(db_session, "sobrevive@provedor.com.br", "viewer")
    archive = make_backup(tmp_path, storage)
    members = read_tar_bytes(archive)
    members["database.dump"] = dump_with_member("tabela_inexistente.bin")
    manifest = json.loads(members["manifest.json"])
    manifest["database_format"] = "psycopg_binary"
    members["manifest.json"] = json.dumps(manifest).encode()
    write_archive(archive, resign(members))

    with pytest.raises(BackupIntegrityError, match="tabela"):
        restore_backup(archive, target_storage_path=tmp_path / "restore")
    db_session.expire_all()
    assert db_session.scalar(text("SELECT count(*) FROM users")) == 1  # nada foi truncado


# ---------------------------------------------------------------------------------------------
# Snapshot consistente e integridade referencial
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def isolated_target() -> Iterator[str]:
    """Banco vazio (só o schema) para restaurar sem tocar o banco de testes."""
    base = source_db_url()
    name = f"ftth_restore_r19_{uuid.uuid4().hex[:6]}"
    admin = psycopg.connect(base.replace("postgresql+psycopg://", "postgresql://"), autocommit=True)
    admin.execute(f'CREATE DATABASE "{name}"')
    target = base.rsplit("/", 1)[0] + f"/{name}"
    env = {**os.environ, "DATABASE_URL": target, "ENVIRONMENT": "test"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
    )
    try:
        yield target
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.close()


def orphan_structures(url: str) -> int:
    engine = create_engine(url)
    with Session(engine) as db:
        return int(
            db.scalar(
                text(
                    "SELECT count(*) FROM structures s LEFT JOIN sites x ON x.id = s.site_id "
                    "WHERE s.site_id IS NOT NULL AND x.id IS NULL"
                )
            )
            or 0
        )


def test_backup_with_concurrent_writes_restores_without_fk_violations(
    tmp_path: Path, isolated_target: str
) -> None:
    """Sem snapshot, o dump de `sites` (antes) e o de `structures` (depois) divergem → órfãos."""
    src = source_db_url().replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(src, autocommit=True) as seed:
        seed.execute("TRUNCATE structures, sites CASCADE")
    inserted = threading.Event()

    def concurrent_write(table: str) -> None:
        if table == "sites" and not inserted.is_set():
            inserted.set()
            with psycopg.connect(src, autocommit=True) as other:
                site_id = uuid.uuid4()
                other.execute(
                    "INSERT INTO sites (id, code, name, kind, status, location, version, created_at, updated_at) "
                    "VALUES (%s, %s, 'Concorrente', 'pop', 'installed', ST_GeomFromText('POINT(-46 -23)', 4326), 1, now(), now())",
                    (site_id, f"S-CONC-{site_id.hex[:6]}"),
                )
                other.execute(
                    "INSERT INTO structures (id, code, kind, status, condition, capacity, location, site_id, version, created_at, updated_at) "
                    "VALUES (%s, %s, 'pole', 'installed', 'ok', 0, ST_GeomFromText('POINT(-46 -23)', 4326), %s, 1, now(), now())",
                    (uuid.uuid4(), f"P-CONC-{site_id.hex[:6]}", site_id),
                )

    dump_dir = tmp_path / "dump"
    dump_file = dump_database_psycopg_binary(
        source_db_url(), dump_dir, on_table_dumped=concurrent_write
    )
    assert inserted.is_set()

    backup_restore.restore_database_psycopg_binary(isolated_target, dump_file)
    assert orphan_structures(isolated_target) == 0


def test_restore_rolls_back_when_the_dump_violates_foreign_keys(
    tmp_path: Path, storage: Path, db_session: Session, isolated_target: str
) -> None:
    site = Site(
        code="S-FK", name="S", kind="pop", status="installed", location="POINT(-46 -23)", version=1
    )
    db_session.add(site)
    db_session.flush()
    db_session.add(
        Structure(
            code="P-FK",
            kind="pole",
            status="installed",
            condition="ok",
            capacity=0,
            location="POINT(-46 -23)",
            site_id=site.id,
            version=1,
        )
    )
    db_session.commit()

    archive = make_backup(tmp_path, storage)
    members = read_tar_bytes(archive)
    manifest = json.loads(members["manifest.json"])
    if manifest["database_format"] != "psycopg_binary":
        pytest.skip("pg_dump disponível: o caminho psycopg não é exercitado")

    # substitui sites.bin por um dump VAZIO de sites → structures ficam órfãs
    src = source_db_url().replace("postgresql+psycopg://", "postgresql://")
    with (
        psycopg.connect(src) as conn,
        conn.cursor() as cur,
        cur.copy("COPY (SELECT * FROM sites WHERE false) TO STDOUT (FORMAT binary)") as copy,
    ):
        empty = b"".join(bytes(chunk) for chunk in copy)
    outer = io.BytesIO(members["database.dump"])
    rebuilt = io.BytesIO()
    with (
        tarfile.open(fileobj=outer, mode="r") as old,
        tarfile.open(fileobj=rebuilt, mode="w") as new,
    ):
        for m in old.getmembers():
            data = empty if m.name == "sites.bin" else old.extractfile(m).read()  # type: ignore[union-attr]
            info = tarfile.TarInfo(m.name)
            info.size = len(data)
            new.addfile(info, io.BytesIO(data))
    members["database.dump"] = rebuilt.getvalue()
    write_archive(archive, resign(members))

    with pytest.raises(BackupIntegrityError, match="integridade referencial"):
        restore_backup(
            archive, target_db_url=isolated_target, target_storage_path=tmp_path / "restore"
        )
    # a transação foi revertida: o alvo continua vazio (sem dados parciais)
    engine = create_engine(isolated_target)
    with Session(engine) as db:
        assert db.scalar(text("SELECT count(*) FROM structures")) == 0


# ---------------------------------------------------------------------------------------------
# Criptografia do pacote
# ---------------------------------------------------------------------------------------------


def test_encrypted_backup_roundtrip_and_no_plaintext_leak(
    tmp_path: Path, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", ENC_KEY)
    get_settings.cache_clear()
    archive = make_backup(tmp_path, storage)
    assert archive.name.endswith(".enc")
    assert not list((tmp_path / "bkp").glob("*.tar.gz"))  # o texto claro não fica no disco
    raw = archive.read_bytes()
    assert b"manifest.json" not in raw and b"conteudo do anexo" not in raw
    assert (archive.stat().st_mode & 0o777) == 0o600

    manifest = restore_backup(archive, target_storage_path=tmp_path / "restore", target_db_url=None)
    assert manifest.attachments_count == 1
    assert (tmp_path / "restore" / "attachments" / "foto.txt").read_text() == "conteudo do anexo"


def test_encrypted_backup_rejects_wrong_key_tampering_and_missing_key(
    tmp_path: Path, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", ENC_KEY)
    get_settings.cache_clear()
    archive = make_backup(tmp_path, storage)

    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", "aa" * 32)
    get_settings.cache_clear()
    with pytest.raises(BackupIntegrityError):
        restore_backup(archive, target_storage_path=tmp_path / "r1")

    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", ENC_KEY)
    get_settings.cache_clear()
    raw = bytearray(archive.read_bytes())
    raw[len(raw) // 2] ^= 0x01  # 1 bit adulterado no meio do pacote
    tampered = tmp_path / "tampered.tar.gz.enc"
    tampered.write_bytes(bytes(raw))
    with pytest.raises(BackupIntegrityError):
        restore_backup(tampered, target_storage_path=tmp_path / "r2")

    truncated = tmp_path / "truncated.tar.gz.enc"
    truncated.write_bytes(archive.read_bytes()[:-40])  # cortado no fim
    with pytest.raises(BackupIntegrityError):
        restore_backup(truncated, target_storage_path=tmp_path / "r3")

    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY")
    get_settings.cache_clear()
    with pytest.raises(BackupIntegrityError, match="BACKUP_ENCRYPTION_KEY"):
        restore_backup(archive, target_storage_path=tmp_path / "r4")


def test_prune_keeps_encrypted_and_plain_backups_by_recency(tmp_path: Path) -> None:
    bdir = tmp_path / "bk"
    bdir.mkdir()
    for i, suffix in enumerate((".tar.gz", ".tar.gz.enc", ".tar.gz", ".tar.gz.enc")):
        f = bdir / f"ftth_backup_2026010{i}_000000{suffix}"
        f.write_text("x")
        os.utime(f, (1_000_000 + i, 1_000_000 + i))
    removed = backup_restore.prune_old_backups(bdir, keep_count=2)
    assert len(removed) == 2 and len(list(bdir.iterdir())) == 2
