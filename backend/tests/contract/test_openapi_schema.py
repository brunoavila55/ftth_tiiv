import inspect
import json
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import create_app


def test_openapi_json_matches_app_schema() -> None:
    """Detecta drift entre a aplicação FastAPI e o arquivo exportado contracts/openapi.json."""
    app = create_app()
    current_schema = app.openapi()

    contracts_file = (
        Path(__file__).resolve().parent.parent.parent.parent / "contracts" / "openapi.json"
    )
    assert contracts_file.exists(), "O arquivo contracts/openapi.json deve existir no repositório."

    exported_content = contracts_file.read_text(encoding="utf-8")
    exported_schema = json.loads(exported_content)

    assert current_schema == exported_schema, (
        "O schema OpenAPI da aplicação divergiu de contracts/openapi.json! "
        "Execute 'uv run python scripts/export_openapi.py' para atualizar o contrato."
    )


def test_operation_ids_are_unique() -> None:
    """Garante que todo endpoint possui um operation_id único e determinístico."""
    app = create_app()
    schema = app.openapi()
    operation_ids: list[str] = []

    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            if method in ("get", "post", "patch", "delete", "put"):
                op_id = operation.get("operationId") or operation.get("operation_id")
                assert op_id is not None, (
                    f"Rota {method.upper()} {path} não possui operation_id definido"
                )
                operation_ids.append(op_id)

    duplicates = [x for x in operation_ids if operation_ids.count(x) > 1]
    assert len(duplicates) == 0, f"Existem operation_ids duplicados no OpenAPI: {set(duplicates)}"


def test_pagination_parameters_have_strict_limits() -> None:
    """Garante que nenhum endpoint possui paginação sem limite máximo (máx <= 200)."""
    app = create_app()
    schema = app.openapi()

    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            for param in operation.get("parameters", []):
                if param.get("name") == "page_size":
                    p_schema = param.get("schema", {})
                    max_limit = p_schema.get("maximum")
                    assert max_limit is not None and max_limit <= 200, (
                        f"Parâmetro page_size na rota {method.upper()} {path} "
                        f"deve ter limite máximo definido menor ou igual a 200."
                    )


def test_units_are_explicit_in_schema_fields() -> None:
    """Valida convenção de unidades explícitas: *_m, *_db, *_dbm, wavelength_nm."""
    app = create_app()
    schema = app.openapi()
    component_schemas = schema.get("components", {}).get("schemas", {})

    unit_suffixes = ("_m", "_db", "_dbm", "_db_per_km", "wavelength_nm", "_bytes", "_ms")
    descriptor_exceptions = ("length_source", "parameter_source")

    # Verifica se campos de grandezas físicas utilizam convenção de nomes
    for schema_name, s_def in component_schemas.items():
        properties = s_def.get("properties", {})
        for prop_name in properties:
            if prop_name in descriptor_exceptions:
                continue
            # Se for campo de perda, comprimento ou potência, deve conter unidade
            if any(
                term in prop_name for term in ("length", "loss", "power", "margin", "attenuation")
            ):
                has_unit = any(
                    prop_name.endswith(suffix) or prop_name == suffix for suffix in unit_suffixes
                )
                assert has_unit, (
                    f"Propriedade '{prop_name}' no schema '{schema_name}' não possui unidade explícita "
                    f"(esperado: *_m, *_db, *_dbm)"
                )


def test_no_pending_endpoint_stubs() -> None:
    """Nenhuma rota publicada no contrato pode continuar delegando para um stub 501."""
    app = create_app()
    pending_routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and "pending_endpoint" in inspect.getsource(route.endpoint):
            pending_routes.append(f"{','.join(sorted(route.methods or []))} {route.path}")
    assert pending_routes == [], f"Rotas ainda não implementadas: {pending_routes}"
