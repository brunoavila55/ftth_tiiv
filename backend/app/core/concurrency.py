"""Concorrência otimista (If-Match) — ponto único de validação (EST-21).

Duas camadas complementares:

1. `parse_if_match`/`check_if_match`: validação rápida do cabeçalho contra a versão carregada
   (428 se ausente, 412 se inválido/defasado).
2. Atomicidade: `VersionedModelMixin` (app/db/base.py) usa `version_id_col`, então o UPDATE/DELETE de
   toda entidade versionada é `... WHERE id = :id AND version = :versão_lida`. Se outra transação
   gravou entre a leitura e o commit, o SQLAlchemy levanta `StaleDataError` (mapeado para 412 em
   core/errors.py). Assim a checagem deixa de ser check-then-act: dois PATCH com o mesmo If-Match
   resultam em exatamente um 200 e um 412.
"""

from collections.abc import Callable

from app.core.errors import PreconditionFailedError, PreconditionRequiredError

# Gancho de teste: executado logo após cada checagem bem-sucedida (permite sincronizar duas
# requisições concorrentes exatamente entre "checou" e "gravou"). Vazio em produção.
_after_check_hooks: list[Callable[[], None]] = []


def parse_if_match(if_match: str | None) -> int:
    """Extrai a versão de um If-Match (aceita `"3"`, `3`, `'3'` e `W/"3"`)."""
    if if_match is None or not if_match.strip():
        raise PreconditionRequiredError(
            "O cabeçalho If-Match com a versão do recurso é obrigatório para esta operação."
        )
    raw = if_match.strip()
    if raw[:2].upper() == "W/":
        raw = raw[2:]
    raw = raw.strip().strip('"').strip("'").strip()
    try:
        return int(raw)
    except ValueError:
        raise PreconditionFailedError(
            f"Valor de If-Match inválido: '{if_match}'. Esperado um número inteiro de versão."
        ) from None


def check_if_match(if_match: str | None, current_version: int) -> None:
    """Confere o If-Match contra a versão atual do recurso (428/412)."""
    expected = parse_if_match(if_match)
    if current_version != expected:
        raise PreconditionFailedError(
            f"Conflito de versão: a versão atual do recurso é {current_version}, "
            f"mas If-Match informou {expected}."
        )
    for hook in list(_after_check_hooks):
        hook()
