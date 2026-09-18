"""Leitura de uploads com teto de tamanho (evita carregar corpos arbitrariamente grandes)."""

from fastapi import HTTPException, UploadFile, status

_CHUNK_SIZE = 64 * 1024


async def read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Lê o upload em blocos e aborta com 413 assim que ultrapassar `max_bytes`."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_CHUNK_SIZE):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Arquivo excede o limite máximo permitido de {max_bytes} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def read_upload_limited_sync(file: UploadFile, max_bytes: int) -> bytes:
    """Versão síncrona (handlers `def`, executados no threadpool) de `read_upload_limited`."""
    chunks: list[bytes] = []
    total = 0
    while chunk := file.file.read(_CHUNK_SIZE):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Arquivo excede o limite máximo permitido de {max_bytes} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)
