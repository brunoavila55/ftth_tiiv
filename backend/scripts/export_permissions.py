#!/usr/bin/env python3
"""Exporta a matriz de permissões (fonte única: app/core/permissions.py) para o frontend.

Gera, de forma determinística:
- contracts/permissions.json                        (contrato compartilhado, como openapi.json)
- frontend/src/lib/permissions/rbac.generated.ts    (tipos e matriz consumidos pela UI)

O backend continua sendo a autoridade: a UI só esconde/desabilita ações; toda rota exige a
permissão no servidor. Rode após alterar a matriz; `tests/contract/test_permissions_contract.py`
falha se os arquivos versionados divergirem.
"""

import json
import sys
from pathlib import Path

from app.core.permissions import ROLE_PERMISSIONS

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
JSON_PATH = REPO_ROOT / "contracts" / "permissions.json"
TS_PATH = REPO_ROOT / "frontend" / "src" / "lib" / "permissions" / "rbac.generated.ts"


def build_matrix() -> dict[str, list[str]]:
    return {role.value: sorted(perms) for role, perms in sorted(ROLE_PERMISSIONS.items())}


def render_json(matrix: dict[str, list[str]]) -> str:
    return json.dumps(matrix, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_ts(matrix: dict[str, list[str]]) -> str:
    all_permissions = sorted({p for perms in matrix.values() for p in perms})
    lines = [
        "// GERADO por backend/scripts/export_permissions.py a partir de backend/app/core/permissions.py.",
        "// NÃO edite à mão: rode `uv run python scripts/export_permissions.py` no backend.",
        "",
        "export const PERMISSIONS = [",
        *[f'  "{p}",' for p in all_permissions],
        "] as const;",
        "",
        "export const ROLE_PERMISSIONS = {",
    ]
    for role, perms in matrix.items():
        lines.append(f"  {role}: [")
        lines.extend(f'    "{p}",' for p in perms)
        lines.append("  ],")
    lines += ["} as const;", ""]
    return "\n".join(lines)


def export_permissions() -> int:
    matrix = build_matrix()
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(render_json(matrix), encoding="utf-8")
    TS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TS_PATH.write_text(render_ts(matrix), encoding="utf-8")
    print(f"[+] Matriz de permissões exportada: {JSON_PATH} e {TS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(export_permissions())
