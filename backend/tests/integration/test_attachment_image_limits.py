"""R07 (PERF-04): upload de imagem sem bloquear o event loop e sem bombas de descompressão."""

import io
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image, ImageFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage_backend import get_storage_backend
from app.modules.attachments import service as attachments_service
from app.modules.inventory.models import Site
from tests.conftest import create_test_user, login_test_client


@pytest.fixture
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    get_storage_backend.cache_clear()
    return tmp_path


@pytest.fixture
def uploader(client: TestClient, db_session: Session, storage: Path) -> Iterator[tuple[str, str]]:
    site = Site(
        code="SITE-IMG", name="Site", kind="pop", status="installed", location="POINT(-46 -23)"
    )
    db_session.add(site)
    create_test_user(db_session, "tech_img@provedor.com.br", "technician")
    db_session.commit()
    csrf = login_test_client(client, "tech_img@provedor.com.br")
    yield str(site.id), csrf


def png_bytes(width: int, height: int, mode: str = "L") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (width, height), 0).save(buf, format="PNG", compress_level=9)
    return buf.getvalue()


def upload(client: TestClient, site_id: str, csrf: str, data: bytes, name: str = "foto.png"):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/attachments",
        data={"entity_id": site_id, "entity_type": "site"},
        files={"file": (name, io.BytesIO(data), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )


def stored_files(storage: Path) -> list[Path]:
    return [p for p in storage.rglob("*") if p.is_file()]


def test_normal_upload_still_creates_attachment_and_thumbnail(
    client: TestClient, uploader: tuple[str, str], storage: Path
) -> None:
    site_id, csrf = uploader
    resp = upload(client, site_id, csrf, png_bytes(800, 600, "RGB"))
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["thumbnail_url"]
    assert len(stored_files(storage)) == 2  # original + miniatura


def test_image_above_pixel_limit_is_rejected_without_decoding_or_writing(
    client: TestClient,
    uploader: tuple[str, str],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site_id, csrf = uploader
    monkeypatch.setenv("MAX_IMAGE_PIXELS", "1000000")  # 1 Mpx
    get_settings.cache_clear()
    data = png_bytes(2000, 2000)  # 4 Mpx, poucos KiB

    def forbid(*args: object, **kwargs: object) -> None:
        raise AssertionError("a imagem não pode ser decodificada antes da validação de dimensões")

    monkeypatch.setattr(ImageFile.ImageFile, "load", forbid)
    monkeypatch.setattr(attachments_service, "generate_thumbnail_image", forbid)

    resp = upload(client, site_id, csrf, data)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "pixels" in resp.json()["detail"].lower() or "megapixel" in resp.json()["detail"].lower()
    assert stored_files(storage) == []


def test_decompression_bomb_returns_422_not_500(
    client: TestClient, uploader: tuple[str, str], storage: Path
) -> None:
    site_id, csrf = uploader
    resp = upload(client, site_id, csrf, png_bytes(14000, 14000, "1"))
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert stored_files(storage) == []


def test_corrupt_image_with_valid_magic_returns_422(
    client: TestClient, uploader: tuple[str, str], storage: Path
) -> None:
    site_id, csrf = uploader
    truncated = png_bytes(400, 400)[:60]
    resp = upload(client, site_id, csrf, truncated)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert stored_files(storage) == []


def test_body_is_cut_at_max_upload_size_with_413(
    client: TestClient,
    uploader: tuple[str, str],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site_id, csrf = uploader
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "2048")
    get_settings.cache_clear()
    resp = upload(client, site_id, csrf, b"\x89PNG\r\n\x1a\n" + b"0" * 10_000)
    assert resp.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert stored_files(storage) == []


def test_health_stays_responsive_during_slow_image_processing(
    client: TestClient,
    uploader: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Se o handler bloqueasse o event loop, /health/live esperaria o processamento (0,6 s)."""
    site_id, csrf = uploader
    real_thumb = attachments_service.generate_thumbnail_image

    def slow_thumbnail(content: bytes, mime_type: str) -> bytes | None:
        time.sleep(0.6)
        return real_thumb(content, mime_type)

    monkeypatch.setattr(attachments_service, "generate_thumbnail_image", slow_thumbnail)
    data = png_bytes(400, 400, "RGB")
    result: dict[str, int] = {}
    worker = threading.Thread(
        target=lambda: result.update(status=upload(client, site_id, csrf, data).status_code)
    )
    worker.start()
    time.sleep(0.2)  # o upload já está dentro do processamento lento

    latencies = []
    for _ in range(3):
        t0 = time.perf_counter()
        assert client.get("/health/live").status_code == status.HTTP_200_OK
        latencies.append(time.perf_counter() - t0)
    worker.join()

    assert result["status"] == status.HTTP_201_CREATED
    assert max(latencies) < 0.1, latencies


def test_generate_thumbnail_image_enforces_pixel_limit_on_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N-04: defesa em profundidade — um novo chamador não herda o risco de decodificar uma bomba."""
    monkeypatch.setenv("MAX_IMAGE_PIXELS", "10000")
    get_settings.cache_clear()
    decoded: list[bool] = []
    real_convert = Image.Image.convert

    def spy_convert(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        decoded.append(True)
        return real_convert(self, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "convert", spy_convert)

    assert attachments_service.generate_thumbnail_image(png_bytes(200, 200), "image/png") is None
    assert decoded == []  # rejeitada pelo cabeçalho, sem decodificar
    assert attachments_service.generate_thumbnail_image(png_bytes(50, 50), "image/png") is not None
