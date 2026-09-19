"""Auditoria central de mutações (EST-10 / SEC-17).

Mecanismo em duas peças, sem copiar chamadas em cada handler:

1. `audit_mutation` (dependência dos routers autenticados): para POST/PUT/PATCH/DELETE registra em
   `db.info["audit_ctx"]` quem (ator), qual requisição (request_id) e qual recurso (rota).
2. Listener `before_commit` da Session: no primeiro commit da requisição que tenha alterações reais
   (novas/alteradas/removidas), acrescenta UM `AuditEvent` **na mesma transação** — se a operação der
   rollback, o evento some junto; se o serviço já gravou um evento explícito (mais rico, ex.:
   `customer:created`), o genérico não é criado (exatamente 1 evento por chamada).

O evento genérico traz um diff seguro (campos sensíveis nunca aparecem) da entidade principal e a
contagem de linhas afetadas nas demais tabelas.
"""

from __future__ import annotations

import decimal
import enum
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from fastapi import Depends, Request
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import SENSITIVE_KEYS, sanitize_audit_payload
from app.modules.identity.models import User

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Tabelas de infraestrutura/ruído: mudanças só nelas não são "a operação" auditada
IGNORED_TABLES = frozenset(
    {"audit_events", "login_attempts", "user_sessions", "network_topology_state"}
)
NOISE_FIELDS = frozenset({"created_at", "updated_at", "version"})

# Primeiro segmento da rota → tabela da entidade principal (quando difere do nome do segmento)
RESOURCE_TABLE_ALIASES = {
    "measurements": "optical_measurements",
    "imports": "import_previews",
    "exports": "async_jobs",
    "jobs": "async_jobs",
}
MAX_STRING_LENGTH = 300
MAX_ACTION_LENGTH = 50


@dataclass
class AuditContext:
    actor_id: uuid.UUID | None
    actor_name: str
    request_id: str | None
    method: str
    path_template: str
    path_params: dict[str, Any]
    recorded: bool = False  # já existe um evento (genérico ou explícito) para esta requisição
    # Mudanças acumuladas a cada flush (uma requisição pode fazer vários flush antes do commit)
    created: list[Any] = field(default_factory=list)
    updated: dict[int, tuple[Any, dict[str, Any]]] = field(default_factory=dict)
    deleted: list[tuple[str, uuid.UUID | None, dict[str, Any]]] = field(default_factory=list)

    def reset_changes(self) -> None:
        self.created.clear()
        self.updated.clear()
        self.deleted.clear()


def audit_mutation(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Dependência dos routers autenticados: prepara o contexto de auditoria de mutações."""
    if request.method not in MUTATING_METHODS:
        return
    route = request.scope.get("route")
    db.info["audit_ctx"] = AuditContext(
        actor_id=current_user.id,
        actor_name=current_user.name,
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path_template=getattr(route, "path_format", request.url.path),
        path_params=dict(request.path_params),
    )


def get_audit_context(db: Session) -> AuditContext | None:
    ctx = db.info.get("audit_ctx")
    return ctx if isinstance(ctx, AuditContext) else None


# ------------------------------------------------------------------------------------------
# Serialização segura
# ------------------------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, enum.Enum):
        return _jsonable(value.value)
    if isinstance(value, str):
        return value if len(value) <= MAX_STRING_LENGTH else value[:MAX_STRING_LENGTH] + "…"
    if isinstance(value, bytes | memoryview) or type(value).__name__.endswith("Element"):
        return "<binário/geometria>"
    return str(value)[:MAX_STRING_LENGTH]


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEYS) or "hash" in lowered


def _tracked(obj: Any) -> bool:
    table = getattr(obj, "__tablename__", None)
    return table is not None and table not in IGNORED_TABLES and not isinstance(obj, AuditEvent)


def _snapshot(obj: Any) -> dict[str, Any]:
    state = inspect(obj)
    return {
        key: _jsonable(state.dict[key])
        for key in (attr.key for attr in state.mapper.column_attrs)
        if key in state.dict
        and key not in NOISE_FIELDS
        and key != "id"
        and state.dict[key] is not None
        and not _is_sensitive(key)
    }


def _diff(obj: Any) -> dict[str, Any]:
    state = inspect(obj)
    diff: dict[str, Any] = {}
    for key in (attr.key for attr in state.mapper.column_attrs):
        if key in NOISE_FIELDS:
            continue
        history = state.attrs[key].history
        if not history.has_changes():
            continue
        if _is_sensitive(key):
            diff[key] = {"changed": True}
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        diff[key] = {"old": _jsonable(old), "new": _jsonable(new)}
    return diff


def _entity_type(table: str) -> str:
    return table[:-1] if table.endswith("s") else table


def _preferred_table(path_template: str, known_tables: set[str]) -> str | None:
    segments = [s for s in path_template.strip("/").split("/") if s]
    if segments[:2] == ["api", "v1"]:
        segments = segments[2:]
    if not segments:
        return None
    first = segments[0].replace("-", "_")
    candidate = RESOURCE_TABLE_ALIASES.get(first, first)
    return candidate if candidate in known_tables else None


def _verb(ctx: AuditContext) -> str:
    segments = [s for s in ctx.path_template.strip("/").split("/") if s]
    if segments[:2] == ["api", "v1"]:
        segments = segments[2:]
    if ctx.method == "POST":
        last = segments[-1] if segments else ""
        if len(segments) > 1 and not last.startswith("{"):
            return last.replace("-", "_")
        return "created"
    return {"PUT": "updated", "PATCH": "updated", "DELETE": "deleted"}.get(ctx.method, "changed")


def _path_entity_id(ctx: AuditContext) -> uuid.UUID | None:
    for name, value in ctx.path_params.items():
        if name.endswith("id"):
            try:
                return uuid.UUID(str(value))
            except ValueError:
                return None
    return None


# ------------------------------------------------------------------------------------------
# Listeners
# ------------------------------------------------------------------------------------------


def _merge_diff(existing: dict[str, Any], new: dict[str, Any]) -> None:
    for key, value in new.items():
        if key in existing and "old" in existing[key] and "new" in value:
            existing[key]["new"] = value["new"]
            if existing[key]["old"] == existing[key]["new"]:
                del existing[key]
        elif key not in existing:
            existing[key] = value


def _collect_after_flush(session: Session, flush_context: Any) -> None:
    """Acumula, a cada flush, o que foi criado/alterado/removido (o histórico ainda está íntegro)."""
    ctx = get_audit_context(session)
    if ctx is None or ctx.recorded:
        return

    if any(isinstance(obj, AuditEvent) for obj in session.new):
        ctx.recorded = True  # evento explícito do serviço: ele é o evento desta chamada
        ctx.reset_changes()
        return

    for obj in session.new:
        if _tracked(obj):
            ctx.created.append(obj)
    for obj in session.dirty:
        if _tracked(obj) and session.is_modified(obj, include_collections=False):
            diff = _diff(obj)
            if not diff:
                continue
            entry = ctx.updated.get(id(obj))
            if entry is None:
                ctx.updated[id(obj)] = (obj, diff)
            else:
                _merge_diff(entry[1], diff)
    for obj in session.deleted:
        if _tracked(obj):
            ctx.deleted.append((obj.__tablename__, getattr(obj, "id", None), _snapshot(obj)))


def _discard_after_rollback(session: Session) -> None:
    ctx = get_audit_context(session)
    if ctx is not None:
        ctx.reset_changes()
        ctx.recorded = False


def _record_generic_event(session: Session) -> None:
    ctx = get_audit_context(session)
    if ctx is None or ctx.recorded:
        return

    session.flush()  # dispara _collect_after_flush com o que ainda estava pendente
    if ctx.recorded:  # um evento explícito apareceu neste último flush
        return
    if not (ctx.created or ctx.updated or ctx.deleted):
        return

    tables = {o.__tablename__ for o in ctx.created}
    tables |= {o.__tablename__ for o, _ in ctx.updated.values()}
    tables |= {table for table, _, _ in ctx.deleted}
    preferred = _preferred_table(ctx.path_template, tables)

    # Entidade principal: a da tabela do recurso da rota; senão a primeira alterada
    primary_kind: str | None = None
    primary_table = primary_id = None
    changes: dict[str, Any] = {}
    counts: dict[str, dict[str, int]] = {}

    def bump(table: str, kind: str) -> None:
        counts.setdefault(table, {})
        counts[table][kind] = counts[table].get(kind, 0) + 1

    candidates: list[tuple[str, str, uuid.UUID | None, dict[str, Any]]] = []
    for obj in ctx.created:
        candidates.append(("created", obj.__tablename__, getattr(obj, "id", None), _snapshot(obj)))
    for obj, diff in ctx.updated.values():
        candidates.append(("updated", obj.__tablename__, getattr(obj, "id", None), diff))
    for table, obj_id, snapshot in ctx.deleted:
        candidates.append(("deleted", table, obj_id, snapshot))

    chosen = next((c for c in candidates if c[1] == preferred), candidates[0])
    primary_kind, primary_table, primary_id, changes = chosen
    for candidate in candidates:
        if candidate is not chosen:
            bump(candidate[1], candidate[0])
    if counts:
        changes = {**changes, "related": counts}

    entity_id = _path_entity_id(ctx) or primary_id or uuid.uuid4()
    entity_type = _entity_type(primary_table)
    action = f"{entity_type}:{_verb(ctx)}"[:MAX_ACTION_LENGTH]

    session.add(
        AuditEvent(
            actor_id=ctx.actor_id,
            actor_name=ctx.actor_name,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=sanitize_audit_payload(changes),
            request_id=ctx.request_id,
        )
    )
    ctx.recorded = True
    ctx.reset_changes()


_registered = False


def register_audit_listeners() -> None:
    """Registra os listeners globais de Session (idempotente)."""
    global _registered
    if not _registered:
        event.listen(Session, "after_flush", _collect_after_flush)
        event.listen(Session, "before_commit", _record_generic_event)
        event.listen(Session, "after_rollback", _discard_after_rollback)
        _registered = True
