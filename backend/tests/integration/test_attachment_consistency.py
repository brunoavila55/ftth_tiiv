"""R20 (EST-09): consistência entre banco e disco nos uploads e no reconciliador."""

import io
import os
import time
import uuid
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core import storage_backend
from app.core.config import get_settings
from app.core.storage_backend import get_storage_backend
from app.modules.attachments import service as attachments_service
from app.modules.attachments.models import Attachment
from app.modules.attachments.service import reconcile_storage_orphans, save_attachment
from app.modules.inventory.models import Site


@pytest.fixture
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    get_storage_backend.cache_clear()
    return tmp_path


@pytest.fixture
def site(db_session: Session) -> Site:
    entity = Site(
        code="SITE-CONS", name="S", kind="pop", status="installed", location="POINT(-46 -23)"
    )
    db_session.add(entity)
    db_session.commit()
    return entity


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def files_on_disk(storage: Path) -> list[Path]:
    return [p for p in (storage / "attachments").rglob("*") if p.is_file()]


def upload(db: Session, site: Site) -> object:
    return save_attachment(
        db,
        entity_id=site.id,
        entity_type="site",
        raw_content=png(),
        original_filename="foto.png",
        user_name="tester",
    )


def test_successful_upload_leaves_exactly_two_final_files_and_no_temp(
    db_session: Session, site: Site, storage: Path
) -> None:
    upload(db_session, site)
    names = sorted(p.name for p in files_on_disk(storage))
    assert len(names) == 2
    assert not any(n.endswith((".uploading", ".tmp")) for n in names)


def test_thumbnail_failure_leaves_no_files_and_no_row(
    db_session: Session, site: Site, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("falha ao gerar miniatura")

    monkeypatch.setattr(attachments_service, "generate_thumbnail_image", boom)
    with pytest.raises(RuntimeError):
        upload(db_session, site)
    assert files_on_disk(storage) == []
    assert db_session.scalar(select(func.count(Attachment.id))) == 0


def test_audit_failure_removes_files_already_written(
    db_session: Session, site: Site, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("falha na auditoria")

    monkeypatch.setattr(attachments_service, "record_audit_event", boom)
    with pytest.raises(RuntimeError):
        upload(db_session, site)
    assert files_on_disk(storage) == []
    db_session.rollback()
    assert db_session.scalar(select(func.count(Attachment.id))) == 0


def test_commit_failure_removes_files_and_leaves_no_row(
    db_session: Session, site: Site, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_commit = Session.commit
    calls = {"n": 0}

    def failing_commit(self: Session) -> None:
        calls["n"] += 1
        if self is db_session and calls["n"] == 1:
            raise OperationalError("COMMIT", {}, Exception("conexão perdida"))
        real_commit(self)

    monkeypatch.setattr(Session, "commit", failing_commit)
    with pytest.raises(OperationalError):
        upload(db_session, site)
    assert files_on_disk(storage) == []
    db_session.rollback()
    assert db_session.scalar(select(func.count(Attachment.id))) == 0


def test_no_file_is_visible_at_its_final_path_before_it_is_complete(
    db_session: Session, site: Site, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A escrita passa por arquivo temporário: o caminho final só existe via os.replace."""
    replaced: list[tuple[str, str]] = []
    real_replace = os.replace

    def spy(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        replaced.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(storage_backend.os, "replace", spy)
    upload(db_session, site)
    assert len(replaced) == 2  # original + miniatura
    assert all(src != dst and src.endswith(".uploading") for src, dst in replaced)


# ---------------------------------------------------------------------------------------------
# Reconciliador: não apaga arquivos recentes (upload em andamento)
# ---------------------------------------------------------------------------------------------


def make_orphan(storage: Path, name: str, age_minutes: float) -> Path:
    directory = storage / "attachments" / "originals"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"orfao")
    stamp = time.time() - age_minutes * 60
    os.utime(path, (stamp, stamp))
    return path


def test_reconciler_keeps_recent_files_and_removes_old_orphans(
    db_session: Session, storage: Path
) -> None:
    grace = get_settings().ATTACHMENT_ORPHAN_GRACE_MINUTES
    assert grace == 15
    recent = make_orphan(storage, f"{uuid.uuid4().hex}.png", age_minutes=1)  # upload em andamento
    old = make_orphan(storage, f"{uuid.uuid4().hex}.png", age_minutes=grace + 5)
    leftover_tmp = make_orphan(storage, f"{uuid.uuid4().hex}.png.uploading", age_minutes=grace + 5)

    result = reconcile_storage_orphans(db_session, dry_run=False)

    assert recent.exists(), "arquivo recente pode pertencer a um upload ainda não commitado"
    assert not old.exists() and not leftover_tmp.exists()
    assert len(result.orphans_removed) == 2


def test_reconciler_dry_run_does_not_delete(db_session: Session, storage: Path) -> None:
    old = make_orphan(storage, f"{uuid.uuid4().hex}.png", age_minutes=60)
    result = reconcile_storage_orphans(db_session, dry_run=True)
    assert old.exists() and len(result.orphans_removed) == 1


def test_grace_period_is_configurable(
    db_session: Session, storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATTACHMENT_ORPHAN_GRACE_MINUTES", "1")
    get_settings.cache_clear()
    path = make_orphan(storage, f"{uuid.uuid4().hex}.png", age_minutes=2)
    reconcile_storage_orphans(db_session, dry_run=False)
    assert not path.exists()


def test_reconciler_never_removes_files_referenced_by_the_database(
    db_session: Session, site: Site, storage: Path
) -> None:
    upload(db_session, site)
    for p in files_on_disk(storage):  # envelhece tudo além da carência
        old = time.time() - 3600
        os.utime(p, (old, old))
    result = reconcile_storage_orphans(db_session, dry_run=False)
    assert result.orphans_removed == []
    assert len(files_on_disk(storage)) == 2
