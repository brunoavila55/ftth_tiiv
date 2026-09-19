"""R27 (EST-20): a matriz de permissões do frontend é gerada do backend e não pode divergir."""

import json

from app.core.permissions import ROLE_PERMISSIONS
from scripts.export_permissions import (
    JSON_PATH,
    TS_PATH,
    build_matrix,
    render_json,
    render_ts,
)
from tests.route_utils import iter_api_routes, required_permissions

REGENERATE = "Execute 'uv run python scripts/export_permissions.py' para atualizar o contrato."


def test_permissions_json_matches_backend_matrix() -> None:
    assert JSON_PATH.exists(), f"contracts/permissions.json deve existir. {REGENERATE}"
    assert json.loads(JSON_PATH.read_text(encoding="utf-8")) == build_matrix(), REGENERATE
    assert JSON_PATH.read_text(encoding="utf-8") == render_json(build_matrix()), REGENERATE


def test_generated_frontend_matrix_matches_backend_matrix() -> None:
    assert TS_PATH.exists(), f"rbac.generated.ts deve existir. {REGENERATE}"
    assert TS_PATH.read_text(encoding="utf-8") == render_ts(build_matrix()), REGENERATE


def test_every_permission_required_by_a_route_exists_in_the_matrix() -> None:
    """Uma rota que exige permissão inexistente ficaria inacessível a todos (nem o admin)."""
    from app.main import create_app

    known = {p for perms in ROLE_PERMISSIONS.values() for p in perms}
    required = {
        p for route in iter_api_routes(create_app()) for p in required_permissions(route.dependant)
    }
    assert required <= known, sorted(required - known)
