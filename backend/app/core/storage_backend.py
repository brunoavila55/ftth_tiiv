"""Backend de armazenamento de anexos/importações/exportações (EST-14).

`STORAGE_BACKEND=local` (padrão) grava em disco/volume — só funciona com réplicas no mesmo host.
`STORAGE_BACKEND=s3` grava em S3/MinIO — necessário para escalar em múltiplos hosts (ADR 0007).
Os dois implementam o mesmo `StorageBackend`; os módulos de anexos/importações/exportações não
sabem qual dos dois está em uso.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import uuid
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import IO, TYPE_CHECKING, NamedTuple, Protocol, cast

from app.core.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Generator


class StorageEntry(NamedTuple):
    key: str
    size_bytes: int
    mtime: float


class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> None: ...

    def save_stream(
        self, key: str, mode: str = "wb", *, encoding: str | None = None, newline: str | None = None
    ) -> contextlib.AbstractContextManager[IO[bytes] | IO[str]]: ...

    def read(self, key: str) -> bytes: ...

    def open_read(self, key: str) -> IO[bytes]:
        """Retorna um objeto binário lível por partes; quem chama é responsável por fechá-lo."""
        ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None:
        """Idempotente: não falha se a chave não existir."""
        ...

    def stat(self, key: str) -> StorageEntry | None: ...

    def list(self, prefix: str) -> Iterator[StorageEntry]: ...

    def local_path(self, key: str) -> Path | None:
        """`Path` real só quando o backend é local (usado para servir download via `FileResponse`
        sem passar pelo processo — quando `None`, quem chama deve usar `open_read`/streaming)."""
        ...

    def presigned_url(
        self,
        key: str,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        expires_in: int = 300,
    ) -> str | None:
        """URL assinada para download direto do bucket, evitando proxy pelo backend em arquivos
        grandes. `None` quando o backend não suporta (local) ou quando não há endpoint público
        configurado — quem chama deve então servir via `open_read`/streaming."""
        ...


def stream_chunks(stream: IO[bytes], chunk_size: int = 65_536) -> Iterator[bytes]:
    """Consome `stream` em blocos e garante o fechamento — usado para servir download via
    `StreamingResponse` quando `local_path()` é `None` (backend S3)."""
    try:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        with contextlib.suppress(Exception):
            stream.close()


class LocalStorage:
    """Disco/volume local. Mesmo comportamento do antigo `core.storage` (EST-08)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root_resolved = root.resolve()

    def _resolve(self, key: str) -> Path:
        """Resolve `key` sob a raiz. Aceita dado legado gravado antes desta abstração: caminho
        absoluto ou relativo ao diretório de trabalho (comportamento herdado). Não normaliza o
        caminho retornado (preserva o valor exato gravado no banco para dados legados)."""
        path = Path(key)
        if path.is_absolute():
            return path
        candidate = self._root / path
        resolved = candidate.resolve()
        if resolved != self._root_resolved and self._root_resolved not in resolved.parents:
            raise ValueError(f"chave de storage fora da raiz: {key!r}")
        if candidate.exists():
            return candidate
        if path.exists():  # legado: relativo ao diretório de trabalho
            return path
        return candidate

    @staticmethod
    def _stage(target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        return target.with_name(f"{target.name}.{uuid.uuid4().hex[:8]}.uploading")

    def save(self, key: str, data: bytes) -> None:
        target = self._resolve(key)
        staged = self._stage(target)
        try:
            staged.write_bytes(data)
            os.replace(staged, target)
        except BaseException:
            with contextlib.suppress(OSError):
                staged.unlink()
            raise

    @contextlib.contextmanager
    def save_stream(
        self, key: str, mode: str = "wb", *, encoding: str | None = None, newline: str | None = None
    ) -> Generator[IO[bytes] | IO[str], None, None]:
        target = self._resolve(key)
        staged = self._stage(target)
        handle: IO[bytes] | IO[str]
        if "b" in mode:
            handle = open(staged, mode)  # noqa: SIM115 (fechado abaixo, em todos os ramos)
        else:
            handle = open(  # noqa: SIM115 (fechado abaixo, em todos os ramos)
                staged, mode, encoding=encoding or "utf-8", newline=newline
            )
        try:
            yield handle
            handle.close()
            os.replace(staged, target)
        except BaseException:
            with contextlib.suppress(Exception):
                handle.close()
            with contextlib.suppress(OSError):
                staged.unlink()
            raise

    def read(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def open_read(self, key: str) -> IO[bytes]:
        return open(self._resolve(key), "rb")  # noqa: SIM115 (fechado por stream_chunks)

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).exists()
        except ValueError:
            return False

    def delete(self, key: str) -> None:
        try:
            path = self._resolve(key)
        except ValueError:
            return
        with contextlib.suppress(OSError):
            path.unlink()

    def stat(self, key: str) -> StorageEntry | None:
        try:
            st = self._resolve(key).stat()
        except (OSError, ValueError):
            return None
        return StorageEntry(key=key, size_bytes=st.st_size, mtime=st.st_mtime)

    def list(self, prefix: str) -> Iterator[StorageEntry]:
        base = self._root / prefix
        resolved_base = base.resolve()
        if (
            resolved_base != self._root_resolved
            and self._root_resolved not in resolved_base.parents
        ):
            return
        if not base.exists():
            return
        for entry in sorted(base.rglob("*")):
            if entry.is_file():
                st = entry.stat()
                yield StorageEntry(
                    key=entry.relative_to(self._root).as_posix(),
                    size_bytes=st.st_size,
                    mtime=st.st_mtime,
                )

    def local_path(self, key: str) -> Path | None:
        return self._resolve(key)

    def presigned_url(
        self,
        key: str,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        expires_in: int = 300,
    ) -> str | None:
        return None


class S3Storage:
    """S3/MinIO via boto3. `save`/`save_stream` só deixam o objeto visível quando completo."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: str,
        use_path_style: bool,
        public_endpoint_url: str = "",
    ) -> None:
        import boto3
        from botocore.client import Config as BotoConfig

        self._bucket = bucket
        boto_config = BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path" if use_path_style else "auto"},
        )
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=boto_config,
        )
        # Assinatura só embute a URL do próprio cliente; quando o endpoint interno (ex.: MinIO em
        # compose.s3.yaml, "http://minio:9000") não é alcançável pelo navegador, um segundo cliente
        # com o endpoint público assina a mesma requisição sem precisar alcançá-lo (gera a URL
        # localmente, não faz chamada de rede) — ver S3_PUBLIC_ENDPOINT_URL.
        self._presign_client = self._client
        self._presigned_downloads_enabled = bool(public_endpoint_url)
        if public_endpoint_url and public_endpoint_url != endpoint_url:
            self._presign_client = boto3.client(
                "s3",
                endpoint_url=public_endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
                config=boto_config,
            )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def save(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    @contextlib.contextmanager
    def save_stream(
        self, key: str, mode: str = "wb", *, encoding: str | None = None, newline: str | None = None
    ) -> Generator[IO[bytes] | IO[str], None, None]:
        text = "b" not in mode
        tmp: IO[bytes] | IO[str]
        if text:
            tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
                mode="w", delete=False, encoding=encoding or "utf-8", newline=newline
            )
        else:
            tmp = tempfile.NamedTemporaryFile(mode="wb", delete=False)  # noqa: SIM115
        tmp_path = tmp.name
        try:
            yield tmp
            tmp.close()
        except BaseException:
            with contextlib.suppress(Exception):
                tmp.close()
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
        try:
            self._client.upload_file(tmp_path, self._bucket, key)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)

    def read(self, key: str) -> bytes:
        body: bytes = self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        return body

    def open_read(self, key: str) -> IO[bytes]:
        body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"]
        return cast("IO[bytes]", body)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def stat(self, key: str) -> StorageEntry | None:
        from botocore.exceptions import ClientError

        try:
            head = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError:
            return None
        return StorageEntry(
            key=key,
            size_bytes=head["ContentLength"],
            mtime=head["LastModified"].timestamp(),
        )

    def list(self, prefix: str) -> Iterator[StorageEntry]:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield StorageEntry(
                    key=obj["Key"],
                    size_bytes=obj["Size"],
                    mtime=obj["LastModified"].timestamp(),
                )

    def local_path(self, key: str) -> Path | None:
        return None

    def presigned_url(
        self,
        key: str,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        expires_in: int = 300,
    ) -> str | None:
        if not self._presigned_downloads_enabled:
            return None
        params: dict[str, str] = {"Bucket": self._bucket, "Key": key}
        if content_type:
            params["ResponseContentType"] = content_type
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        url: str = self._presign_client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires_in
        )
        return url


@lru_cache
def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage(
            bucket=settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            region=settings.S3_REGION,
            use_path_style=settings.S3_USE_PATH_STYLE,
            public_endpoint_url=settings.S3_PUBLIC_ENDPOINT_URL,
        )
    return LocalStorage(Path(settings.STORAGE_PATH))
