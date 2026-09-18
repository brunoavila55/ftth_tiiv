"""R06 (EST-11): todo corpo de requisição tem teto de tamanho.

Guarda genérico sobre o OpenAPI: strings precisam de `maxLength`, listas de `maxItems` e inteiros
de `maximum`, para que nenhuma rota volte a aceitar entrada ilimitada.
"""

from typing import Any

from app.main import create_app

# Strings sem maxLength aceitas, com justificativa:
#  - format uuid/date-time/date/binary/email: validados por formato (e-mail ≤ 254 pelo validador);
#  - identificadores `*_id` / `id`: serão tipados como uuid.UUID na etapa R25 (validação de UUID).
EXEMPT_FORMATS = {"uuid", "date-time", "date", "binary", "email"}


def _is_id_field(name: str) -> bool:
    base = name.removesuffix("[]")
    return base == "id" or base.endswith(("_id", "_ids"))


def _request_schema_names(schema: dict[str, Any]) -> set[str]:
    comps = schema["components"]["schemas"]
    roots: set[str] = set()
    for item in schema["paths"].values():
        for op in item.values():
            if not isinstance(op, dict):
                continue
            for content in (op.get("requestBody") or {}).get("content", {}).values():
                ref = content["schema"].get("$ref")
                if ref:
                    roots.add(ref.split("/")[-1])

    seen: set[str] = set()

    def visit(name: str) -> None:
        if name in seen:
            return
        seen.add(name)

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if "$ref" in node:
                    visit(node["$ref"].split("/")[-1])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(comps[name])

    for root in roots:
        visit(root)
    return seen


def _violations(model: str, prop: str, spec: dict[str, Any]) -> list[str]:
    if "$ref" in spec or "enum" in spec or "const" in spec:
        return []
    found: list[str] = []
    for alt in spec.get("anyOf", []) + spec.get("oneOf", []) + spec.get("allOf", []):
        found += _violations(model, prop, alt)
    kind = spec.get("type")
    label = f"{model}.{prop}"
    if kind == "string" and "maxLength" not in spec and "contentMediaType" not in spec:
        if spec.get("format") not in EXEMPT_FORMATS and not _is_id_field(prop):
            found.append(f"{label}: string sem maxLength")
    elif kind == "array":
        if "maxItems" not in spec:
            found.append(f"{label}: lista sem maxItems")
        found += _violations(model, prop + "[]", spec.get("items", {}))
    elif kind == "integer" and "maximum" not in spec and "exclusiveMaximum" not in spec:
        found.append(f"{label}: inteiro sem maximum")
    return found


def test_all_request_bodies_have_size_caps() -> None:
    schema = create_app().openapi()
    comps = schema["components"]["schemas"]
    problems: list[str] = []
    for name in sorted(_request_schema_names(schema)):
        for prop, spec in comps[name].get("properties", {}).items():
            problems += _violations(name, prop, spec)
    assert not problems, "Campos de requisição sem teto:\n" + "\n".join(problems)
