"""EST-14: `LocalStorage` (disco, padrão) e `S3Storage` (MinIO/S3, opt-in) implementam o mesmo
`StorageBackend` — a mesma bateria de testes roda para os dois."""

from collections.abc import Iterator
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from app.core.storage_backend import LocalStorage, S3Storage, StorageBackend


@pytest.fixture
def local_backend(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


@pytest.fixture
def s3_backend() -> Iterator[S3Storage]:
    with mock_aws():
        yield S3Storage(
            bucket="ftth-test-bucket",
            endpoint_url="",
            access_key="test",
            secret_key="test",
            region="us-east-1",
            use_path_style=True,
        )


@pytest.fixture(params=["local", "s3"])
def backend(request: pytest.FixtureRequest) -> Iterator[StorageBackend]:
    if request.param == "local":
        yield request.getfixturevalue("local_backend")
    else:
        yield request.getfixturevalue("s3_backend")


def test_save_then_read_roundtrips(backend: StorageBackend) -> None:
    backend.save("attachments/originals/a.png", b"conteudo-binario")
    assert backend.read("attachments/originals/a.png") == b"conteudo-binario"


def test_exists_and_delete_are_idempotent(backend: StorageBackend) -> None:
    key = "imports/x.geojson"
    assert backend.exists(key) is False
    backend.delete(key)  # não deve levantar mesmo sem o arquivo existir

    backend.save(key, b"{}")
    assert backend.exists(key) is True
    backend.delete(key)
    assert backend.exists(key) is False
    backend.delete(key)  # segunda chamada também não levanta


def test_stat_returns_size_and_none_when_missing(backend: StorageBackend) -> None:
    assert backend.stat("exports/nao-existe.csv") is None
    backend.save("exports/1.csv", b"a,b,c\n1,2,3\n")
    entry = backend.stat("exports/1.csv")
    assert entry is not None
    assert entry.size_bytes == len(b"a,b,c\n1,2,3\n")


def test_open_read_streams_full_content(backend: StorageBackend) -> None:
    backend.save("exports/2.csv", b"linha1\nlinha2\n")
    stream = backend.open_read("exports/2.csv")
    try:
        assert stream.read() == b"linha1\nlinha2\n"
    finally:
        stream.close()


def test_save_stream_text_mode_matches_save(backend: StorageBackend) -> None:
    with backend.save_stream("exports/3.csv", mode="w", newline="") as out:
        out.write("a,b\n1,2\n")
    assert backend.read("exports/3.csv") == b"a,b\n1,2\n"


def test_save_stream_discards_on_exception(backend: StorageBackend) -> None:
    with pytest.raises(RuntimeError), backend.save_stream("exports/4.csv", mode="w") as out:
        out.write("parcial")
        raise RuntimeError("falha no meio da escrita")
    assert backend.exists("exports/4.csv") is False


def test_list_returns_only_entries_under_prefix(backend: StorageBackend) -> None:
    backend.save("attachments/originals/a.png", b"1")
    backend.save("attachments/thumbnails/a.webp", b"2")
    backend.save("imports/outro.csv", b"3")

    keys = {entry.key for entry in backend.list("attachments/")}
    assert keys == {"attachments/originals/a.png", "attachments/thumbnails/a.webp"}


def test_list_empty_prefix_returns_nothing(backend: StorageBackend) -> None:
    assert list(backend.list("nao/existe/")) == []


# ---------------------------------------------------------------------------------------------
# Específicos do LocalStorage: atomicidade e proteção de path traversal
# ---------------------------------------------------------------------------------------------


def test_local_save_is_atomic_no_temp_file_left_behind(
    local_backend: LocalStorage, tmp_path: Path
) -> None:
    local_backend.save("attachments/originals/a.png", b"dados")
    files = list((tmp_path / "attachments" / "originals").iterdir())
    assert [f.name for f in files] == ["a.png"]


def test_local_path_returns_real_path(local_backend: LocalStorage, tmp_path: Path) -> None:
    local_backend.save("imports/x.csv", b"a")
    path = local_backend.local_path("imports/x.csv")
    assert path == tmp_path / "imports" / "x.csv"
    assert path.read_bytes() == b"a"


def test_local_rejects_keys_that_escape_the_root(local_backend: LocalStorage) -> None:
    with pytest.raises(ValueError):
        local_backend.save("../fora-da-raiz.txt", b"x")


def test_s3_local_path_is_always_none(s3_backend: S3Storage) -> None:
    s3_backend.save("imports/x.csv", b"a")
    assert s3_backend.local_path("imports/x.csv") is None


def test_s3_bucket_is_created_automatically() -> None:
    with mock_aws():
        S3Storage(
            bucket="outro-bucket",
            endpoint_url="",
            access_key="test",
            secret_key="test",
            region="us-east-1",
            use_path_style=True,
        )
        client = boto3.client("s3", region_name="us-east-1")
        buckets = {b["Name"] for b in client.list_buckets()["Buckets"]}
        assert "outro-bucket" in buckets


# ---------------------------------------------------------------------------------------------
# URLs pré-assinadas (ADR 0007, item 2): desabilitadas por padrão — só ligam com endpoint público
# explícito, porque o MinIO do compose.s3.yaml (S3_ENDPOINT_URL=http://minio:9000) só é alcançável
# dentro da rede Docker, nunca pelo navegador do usuário.
# ---------------------------------------------------------------------------------------------


def test_local_presigned_url_is_always_none(local_backend: LocalStorage) -> None:
    local_backend.save("attachments/a.png", b"dados")
    assert local_backend.presigned_url("attachments/a.png") is None


def test_s3_presigned_url_disabled_without_public_endpoint(s3_backend: S3Storage) -> None:
    s3_backend.save("exports/1.csv", b"a,b\n1,2\n")
    assert s3_backend.presigned_url("exports/1.csv") is None


def test_s3_presigned_url_uses_public_endpoint_when_configured() -> None:
    # `endpoint_url=""` no cliente principal é o único jeito de exercitar S3Storage sob moto (ele só
    # intercepta o endpoint padrão da AWS); o cliente de assinatura, por outro lado, nunca faz
    # chamada de rede (`generate_presigned_url` só monta e assina a URL localmente), então pode
    # apontar para qualquer host público — inclusive um inalcançável neste teste.
    with mock_aws():
        backend = S3Storage(
            bucket="ftth-presign-bucket",
            endpoint_url="",
            access_key="test",
            secret_key="test",
            region="us-east-1",
            use_path_style=True,
            public_endpoint_url="https://minio.exemplo.com.br",
        )
        backend.save("attachments/foto.jpg", b"dados")
        url = backend.presigned_url(
            "attachments/foto.jpg", filename="foto.jpg", content_type="image/jpeg"
        )
        assert url is not None
        assert url.startswith("https://minio.exemplo.com.br/")
        assert "X-Amz-Signature=" in url
        assert "response-content-disposition=attachment%3B" in url
        assert "filename%3D%22foto.jpg%22" in url
        assert "response-content-type=image%2Fjpeg" in url


def test_s3_presign_client_is_reused_when_no_public_endpoint_is_set(s3_backend: S3Storage) -> None:
    assert s3_backend._presign_client is s3_backend._client  # type: ignore[attr-defined]
