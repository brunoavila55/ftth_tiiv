"""Busca textual segura: escape de curingas do LIKE e helper único de "contém" (PERF-06).

O termo digitado pelo usuário nunca deve virar padrão: `%`, `_` e `\\` são escapados, então buscar
por `100%` acha o texto literal "100%" (antes, o `%` era curinga e casava qualquer coisa). O padrão
`%termo%` é atendido pelos índices GIN trigram (pg_trgm) criados na migração 0014.
"""

from typing import Any

# Busca global e listagens só usam índice trigram a partir de 3 caracteres
MIN_SEARCH_LENGTH = 3


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains(column: Any, term: str) -> Any:
    """`column ILIKE '%termo%'` com o termo escapado (ESCAPE '\\')."""
    return column.ilike(f"%{escape_like(term.strip())}%", escape="\\")
