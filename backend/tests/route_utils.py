"""Introspecção das rotas do app FastAPI (FastAPI ≥ 0.141 agrupa routers em `_IncludedRouter`)."""

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute


def iter_api_routes(app: FastAPI) -> Iterator[APIRoute]:
    for route in app.routes:
        if type(route).__name__ == "_IncludedRouter":
            yield from route.effective_route_contexts()  # type: ignore[attr-defined]
        elif isinstance(route, APIRoute):
            yield route


def required_permissions(dependant: Dependant) -> set[str]:
    """Permissões RBAC exigidas (via `require_permission`) por uma rota, incluindo sub-dependências."""
    found: set[str] = set()
    for sub in dependant.dependencies:
        perm = getattr(sub.call, "required_permission", None)
        if perm:
            found.add(perm)
        found |= required_permissions(sub)
    return found
