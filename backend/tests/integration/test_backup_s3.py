"""ADR 0007 (item 4 do épico EST-14): backup/restore de anexos quando `STORAGE_BACKEND=s3` —
baixa/restaura o bucket inteiro (MinIO/S3), em vez do volume local, com as mesmas garantias de
integridade (manifesto assinado, checksums) já cobertas por `test_backup_security.py`."""

from pathlib import Path

import pytest
from moto import mock_aws

from app.core.backup_restore import BackupIntegrityError, create_backup, restore_backup
from app.core.config import get_settings
from app.core.storage_backend import get_storage_backend

SIGNING_KEY = "backup-signing-key-de-teste-com-mais-de-trinta-e-dois-caracteres"


@pytest.fixture(autouse=True)
def s3_backend_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKUP_SIGNING_KEY", SIGNING_KEY)
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    # Endpoint real da AWS (moto intercepta por reconhecer o host; um hostname customizado como o
    # do MinIO em produção não seria interceptado e tentaria conexão de rede de verdade).
    # STORAGE_BACKEND=s3 exige S3_ENDPOINT_URL não vazio (config.py); "" seria rejeitado na validação.
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
    monkeypatch.setenv("S3_BUCKET", "ftth-backup-test-bucket")
    monkeypatch.setenv("S3_ACCESS_KEY", "test")
    monkeypatch.setenv("S3_SECRET_KEY", "test")
    get_settings.cache_clear()
    get_storage_backend.cache_clear()
    yield
    get_settings.cache_clear()
    get_storage_backend.cache_clear()


def test_backup_downloads_bucket_and_restore_recovers_deleted_objects(tmp_path: Path) -> None:
    with mock_aws():
        backend = get_storage_backend()
        backend.save("attachments/foto.txt", b"conteudo do anexo")
        backend.save("exports/dados.csv", b"a,b\n1,2\n")

        archive = create_backup(target_dir=tmp_path / "bkp")

        # Simula perda dos objetos (apagados por engano) e restaura a partir do backup do bucket.
        backend.delete("attachments/foto.txt")
        backend.delete("exports/dados.csv")
        assert backend.exists("attachments/foto.txt") is False

        manifest = restore_backup(archive)
        assert manifest.attachments_count == 2
        assert backend.read("attachments/foto.txt") == b"conteudo do anexo"
        assert backend.read("exports/dados.csv") == b"a,b\n1,2\n"


def test_backup_with_empty_bucket_restores_zero_attachments(tmp_path: Path) -> None:
    with mock_aws():
        get_storage_backend()  # garante que o bucket existe
        archive = create_backup(target_dir=tmp_path / "bkp")
        manifest = restore_backup(archive)
        assert manifest.attachments_count == 0


def test_restore_to_bucket_refuses_path_traversal_in_attachment_key(tmp_path: Path) -> None:
    """Mesma proteção do caminho local (`test_attachments_archive_with_path_traversal_is_refused`),
    agora para o backend S3: o nome do membro no `attachments.tar.gz` é validado antes de gravar
    qualquer objeto no bucket."""
    import io
    import json
    import tarfile

    from app.core.backup_restore import sign_manifest

    with mock_aws():
        backend = get_storage_backend()
        backend.save("attachments/foto.txt", b"conteudo do anexo")
        archive = create_backup(target_dir=tmp_path / "bkp")

        with tarfile.open(archive, "r:gz") as tar:
            members = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}  # type: ignore[union-attr]

        att = io.BytesIO()
        with tarfile.open(fileobj=att, mode="w:gz") as tar:
            info = tarfile.TarInfo("../../escape.txt")
            info.size = 3
            tar.addfile(info, io.BytesIO(b"pwn"))
        members["attachments.tar.gz"] = att.getvalue()

        manifest = json.loads(members["manifest.json"])
        manifest.pop("signature", None)
        import hashlib

        manifest["database_checksum_sha256"] = hashlib.sha256(members["database.dump"]).hexdigest()
        manifest["attachments_checksum_sha256"] = hashlib.sha256(
            members["attachments.tar.gz"]
        ).hexdigest()
        manifest["attachments_count"] = 1
        manifest["signature"] = sign_manifest(manifest, SIGNING_KEY)
        members["manifest.json"] = json.dumps(manifest).encode()

        with tarfile.open(archive, "w:gz") as tar:
            for name, data in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))

        with pytest.raises(BackupIntegrityError):
            restore_backup(archive)
        assert backend.exists("escape.txt") is False
