"""Caminhos do armazenamento local (`STORAGE_PATH`): tudo é gravado relativo à raiz (EST-08)."""

from pathlib import Path

from app.core.config import get_settings


def storage_root() -> Path:
    return Path(get_settings().STORAGE_PATH)


def ensure_storage_dir(name: str) -> Path:
    """Diretório `<STORAGE_PATH>/<name>` (criado se preciso)."""
    directory = storage_root() / name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def resolve_storage_path(stored: str | Path) -> Path:
    """Resolve um caminho gravado no banco.

    Caminhos novos são relativos à raiz do storage (ex.: `imports/<hash>.geojson`). Para dados
    antigos, aceita caminho absoluto e caminho relativo ao diretório de trabalho (o comportamento
    anterior gravava `storage/imports/...` relativo ao CWD), sem exigir migração de dados.
    """
    path = Path(stored)
    if path.is_absolute():
        return path
    candidate = storage_root() / path
    if candidate.exists():
        return candidate
    if path.exists():  # legado: relativo ao CWD
        return path
    return candidate
