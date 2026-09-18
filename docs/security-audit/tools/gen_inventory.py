#!/usr/bin/env python3
"""Gera docs/security-audit/inventario-rotas.md a partir de evidencias/routes.json.

routes.json é produzido por tools/enum_routes.py (introspecção do app FastAPI, sem executar handlers).
Papéis são derivados de app.core.permissions.ROLE_PERMISSIONS (importado do projeto, somente leitura).

Uso (venv fora do repositório):
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend /tmp/audit-env/venv/bin/python \
      docs/security-audit/tools/gen_inventory.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "docs" / "security-audit"
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.permissions import ROLE_PERMISSIONS  # noqa: E402

ROLE_ORDER = ["viewer", "technician", "engineer", "admin"]
ROLE_PT = {"viewer": "viewer", "technician": "technician", "engineer": "engineer", "admin": "admin"}

# Referências indiretas a IDs (query/body) — levantadas por leitura dos schemas/serviços.
INDIRECT_IDS: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/structures"): "body.site_id",
    ("PATCH", "/api/v1/structures/{structure_id}"): "body.site_id",
    ("POST", "/api/v1/devices"): "body.site_id, body.structure_id",
    ("POST", "/api/v1/ports"): "body.device_id, body.structure_id",
    ("POST", "/api/v1/cable-segments"): "body.cable_id, body.origin/destination_structure_id",
    ("POST", "/api/v1/cable-segments/{segment_id}/split"): "body.access_structure_id, body.cut_fiber_ids[]",
    ("POST", "/api/v1/cable-segments/{segment_id}/split/preview"): "body.access_structure_id, body.cut_fiber_ids[]",
    ("POST", "/api/v1/connections"): "body.terminal_a_id/terminal_b_id, body.structure_id",
    ("POST", "/api/v1/connections/batch"): "body.structure_id, body.operations[].terminal_*_id",
    ("GET", "/api/v1/connections"): "query.structure_id",
    ("POST", "/api/v1/service-links"): "body.customer_id, body.onu_device_id, body.port_id",
    ("GET", "/api/v1/service-links"): "query.customer_id, query.port_id",
    ("POST", "/api/v1/measurements"): "body.terminal_id, body.service_link_id",
    ("POST", "/api/v1/optical/budgets"): "body.service_link_id, body.start_terminal_id, body.profile_id",
    ("POST", "/api/v1/optical/simulations"): "body.service_link_id/start_terminal_id, body.overrides[]",
    ("POST", "/api/v1/topology/trace"): "body.start_terminal_id",
    ("POST", "/api/v1/topology/impact"): "body.cable_segment_ids[]",
    ("POST", "/api/v1/attachments"): "form.entity_id + form.entity_type (referência polimórfica)",
    ("GET", "/api/v1/attachments"): "query.entity_id + query.entity_type",
    ("GET", "/api/v1/audit-events"): "query.entity_id, query.actor_id",
    ("GET", "/api/v1/reports/ctos"): "query.site_id",
    ("POST", "/api/v1/imports/{import_id}/commit"): "path.import_id + body.file_hash + header Idempotency-Key",
}

# Veredito por rota: (cat1 isolamento/banco sem tranca, cat2 permissão no navegador, cat3 IDOR)
SINGLE_TENANT = "N/A tenant (instância única); RBAC global"


def classify(r: dict) -> dict:
    m, p = r["methods"][0], r["path"]
    deps = r["deps"]
    perms = [d[1] for d in deps if d[0] == "perm"]
    perms = list(dict.fromkeys(perms))
    has_csrf = any(d[1] == "validate_csrf" for d in deps)
    optional = any(d[1] == "get_optional_current_user" for d in deps)
    user_only = any(d[1] == "get_current_user" for d in deps)

    if perms:
        auth = "Sessão + permissão " + " + ".join(f"`{x}`" for x in perms)
        roles = [ro for ro in ROLE_ORDER if all(x in ROLE_PERMISSIONS_STR[ro] for x in perms)]
        role_txt = ", ".join(roles) if roles else "—"
    elif optional:
        auth = "**Opcional** (anônimo permitido)"
        role_txt = "qualquer (inclui anônimo)"
    elif user_only:
        auth = "Sessão (qualquer papel)"
        role_txt = "qualquer autenticado"
    else:
        auth = "**Nenhuma**"
        role_txt = "público"
    return dict(m=m, p=p, perms=perms, auth=auth, roles=role_txt, csrf=has_csrf)


ROLE_PERMISSIONS_STR = {k.value: set(v) for k, v in ROLE_PERMISSIONS.items()}

PUBLIC_BY_DESIGN = {
    ("GET", "/health/live"), ("GET", "/health/ready"),
    ("GET", "/api/v1/health/live"), ("GET", "/api/v1/health/ready"),
    ("GET", "/api/v1/auth/csrf"), ("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/logout"),
}
STUBS = {
    ("GET", "/api/v1/structures/{structure_id}/occupancy"),
    ("GET", "/api/v1/splitters"), ("POST", "/api/v1/splitters"),
    ("GET", "/api/v1/splitters/{splitter_id}"), ("PATCH", "/api/v1/splitters/{splitter_id}"),
    ("DELETE", "/api/v1/splitters/{splitter_id}"),
    ("GET", "/api/v1/settings"), ("PATCH", "/api/v1/settings"),
}
UUID_500 = {
    ("GET", "/api/v1/customers/{customer_id}"), ("PATCH", "/api/v1/customers/{customer_id}"),
    ("DELETE", "/api/v1/customers/{customer_id}"), ("GET", "/api/v1/service-links"),
    ("GET", "/api/v1/service-links/{link_id}"), ("PATCH", "/api/v1/service-links/{link_id}"),
    ("DELETE", "/api/v1/service-links/{link_id}"), ("POST", "/api/v1/service-links"),
    ("GET", "/api/v1/structures/{structure_id}/cto-occupancy"),
    ("GET", "/api/v1/structures/{structure_id}/connectivity"),
    ("GET", "/api/v1/connections"), ("GET", "/api/v1/connections/{connection_id}"),
    ("DELETE", "/api/v1/connections/{connection_id}"), ("POST", "/api/v1/topology/trace"),
}
CUSTOMER_ROUTES = {(m, p) for (m, p) in UUID_500 if "customers" in p} | {("GET", "/api/v1/customers"), ("POST", "/api/v1/customers")}
CUSTOMER_ROUTES |= {("GET", "/api/v1/service-links"), ("POST", "/api/v1/service-links"),
                    ("GET", "/api/v1/service-links/{link_id}"), ("PATCH", "/api/v1/service-links/{link_id}"),
                    ("DELETE", "/api/v1/service-links/{link_id}")}
ATTACH_ROUTES = {("GET", "/api/v1/attachments"), ("GET", "/api/v1/attachments/{attachment_id}"),
                 ("GET", "/api/v1/attachments/{attachment_id}/download"),
                 ("GET", "/api/v1/attachments/{attachment_id}/thumbnail")}


def verdicts(c: dict, r: dict) -> tuple[str, str, str]:
    key = (c["m"], c["p"])
    ids = r["params"]["path"]
    indirect = INDIRECT_IDS.get(key)
    has_id = bool(ids) or bool(indirect)

    # --- cat.1 Banco sem tranca / isolamento
    if key in STUBS:
        v1 = "ACHADO EST-02 (stub 501 sem auth; allow-by-default)"
    elif key == ("GET", "/api/v1/dashboard/summary"):
        v1 = "ACHADO SEC-01 / PERF-01 (agregação global sem autenticação)"
    elif key == ("GET", "/api/v1/search"):
        v1 = "ACHADO SEC-01 (busca global anônima; clientes só com `customers:read`)"
    elif key == ("GET", "/api/v1/metrics"):
        v1 = "ACHADO SEC-02 (token default público; via Caddy `/api/*`)"
    elif key in CUSTOMER_ROUTES:
        v1 = "ACHADO SEC-03 (PII de clientes com `network:read`; `customers:read` nunca aplicado)"
    elif key == ("GET", "/api/v1/audit-events"):
        v1 = "ACHADO SEC-04 (`changes` de clientes contém phone/email/address; papel technician)"
    elif key in ATTACH_ROUTES:
        v1 = "ACHADO SEC-04 (anexos de `customer` legíveis por technician sem `customers:read`)"
    elif key == ("POST", "/api/v1/exports") or c["p"].startswith("/api/v1/exports/"):
        v1 = "ACHADO SEC-13 (export/download de PII sem auditoria, retenção ou re-checagem do papel)" if c["m"] == "GET" or c["m"] == "POST" else SINGLE_TENANT
    elif key == ("GET", "/api/v1/jobs/{job_id}"):
        v1 = "ACHADO SEC-14 (qualquer papel lê `error_message` cru)"
    elif key in PUBLIC_BY_DESIGN:
        v1 = "N/A (público por design; sem dados de negócio)"
    else:
        v1 = SINGLE_TENANT

    # --- cat.2 Permissão no navegador x servidor
    if key in STUBS or key == ("GET", "/api/v1/dashboard/summary") or key == ("GET", "/api/v1/search"):
        v2 = "ACHADO (servidor não exige auth/permissão; UI não gateia)"
    elif key == ("POST", "/api/v1/exports"):
        v2 = "ok — gate UI `isAdmin` (export-wizard.tsx:29) ↔ servidor `user.role != \"admin\"` p/ camada `customers` (exports/service.py:62)"
    elif c["perms"]:
        v2 = f"ok — servidor valida `{c['perms'][0]}`; UI só tem AuthGuard de sessão (nenhum gate de papel a cruzar)"
        if key in CUSTOMER_ROUTES:
            v2 = "ACHADO SEC-03 — servidor valida `network:*`, não `customers:*` (matriz UI/servidor declara `customers:read` só p/ engineer/admin)"
    elif key in PUBLIC_BY_DESIGN:
        v2 = "N/A (público por design)"
    else:
        v2 = "ok — exige sessão; sem gate de papel na UI"

    # --- cat.3 IDOR
    if not has_id:
        v3 = "N/A (não recebe ID de objeto)"
    else:
        notes = []
        if key in ATTACH_ROUTES or key == ("POST", "/api/v1/attachments"):
            notes.append("ACHADO SEC-04 (sem checagem da permissão da entidade dona)")
        if key in CUSTOMER_ROUTES:
            notes.append("ACHADO SEC-03")
        if key in {("GET", "/api/v1/exports/{export_id}/download")}:
            notes.append("ACHADO SEC-13 (download não checa quem pediu / papel admin)")
        if key == ("GET", "/api/v1/jobs/{job_id}"):
            notes.append("ACHADO SEC-14")
        if key in UUID_500:
            notes.append("ACHADO EST-12 (UUID inválido → HTTP 500)")
        if key in STUBS:
            notes.append("ACHADO EST-02")
        if not notes:
            notes.append("ok — sem dono/tenant por design; existência das referências validada no serviço" if (indirect or ids) else "ok")
        v3 = "; ".join(notes)
    return v1, v2, v3


def main() -> None:
    routes = [r for r in json.load(open(OUT_DIR / "evidencias" / "routes.json")) if "methods" in r]
    lines: list[str] = []
    add = lines.append
    total_handlers = len(routes)
    total_pairs = sum(len(r["methods"]) for r in routes)
    add("# Inventário de superfície — todas as rotas do backend (FastAPI)\n")
    add("> Gerado por `docs/security-audit/tools/gen_inventory.py` a partir de `evidencias/routes.json`.")
    add("> **Método de contagem:** introspecção do objeto `app` (`tools/enum_routes.py`) — percorre `_IncludedRouter.effective_route_contexts()` "
        "(FastAPI 0.141.1), resolve prefixos e dependências **efetivas** (inclui `dependencies=[...]` de decorador e `Depends` de parâmetro) e "
        "extrai a permissão de cada closure `require_permission(...)`. Não executa handlers.")
    add(f"> **Total: {total_handlers} handlers = {total_pairs} pares (método, path).** Fora do inventário (não são `APIRoute`): `/openapi.json`, `/docs`, "
        "`/docs/oauth2-redirect`, `/redoc` (desativados quando `ENVIRONMENT=production`, `main.py:52-54`).\n")
    add("Legenda de veredito: **ok** · **ACHADO ID** (ver `findings.json`) · **N/A** (não aplicável, com motivo). "
        "Categorias: **C1** banco sem tranca/isolamento · **C2** permissão definida no navegador × servidor · **C3** IDOR/posse.\n")

    add("## 1. Contagens\n")
    perm = sum(1 for r in routes if any(d[0] == "perm" for d in r["deps"]))
    none = [r for r in routes if not any(d[1] in ("get_current_user", "get_optional_current_user") or d[0] == "perm" for d in r["deps"])]
    add(f"- Handlers com `require_permission`: **{perm}**")
    add(f"- Handlers sem qualquer dependência de autenticação: **{len(none)}** (7 públicos por design: health×4, `/auth/csrf`, `/auth/login`, `/auth/logout`; "
        "**9 achados**: `dashboard/summary`, 5 stubs de `splitters`, 2 de `settings`, `structures/{id}/occupancy`).")
    add("- Autenticação opcional (anônimo permitido): `GET /api/v1/search`, `GET /api/v1/metrics`.")
    add("- Só `get_current_user` (qualquer papel): `GET /auth/me`, `POST /auth/change-password`, `GET /jobs/{job_id}`.")
    mut = [r for r in routes if set(r["methods"]) & {"POST", "PUT", "PATCH", "DELETE"}]
    nocsrf = [r for r in mut if not any(d[1] == "validate_csrf" for d in r["deps"])]
    add(f"- Handlers mutantes (POST/PATCH/DELETE): **{len(mut)}**; sem `validate_csrf`: **{len(nocsrf)}** "
        "(4 stubs 501 + 5 POSTs de cálculo somente-leitura: `split/preview`, `topology/trace`, `topology/impact`, `optical/budgets`, `optical/simulations`).\n")

    add("## 2. Mecanismos (resumo; detalhes no relatório)\n")
    add("- **Isolamento de tenant:** *não existe* — a aplicação é de organização única (nenhuma tabela possui `tenant_id`/`org_id`/`owner_id`; "
        "`grep -riE 'tenant|org_id|owner_id|created_by' backend/app` → 0 ocorrências). O controle é RBAC global por permissão.")
    add("- **AuthN:** cookie de sessão opaco `ftth_session` (ou `Authorization: Bearer <mesmo token>`), resolvido em `core/dependencies.py:117-142` → "
        "`identity/service.py:119-157`. **AuthZ:** `require_permission()` em `core/dependencies.py:181-195` + matriz em `core/permissions.py:4-80`. "
        "**CSRF:** `validate_csrf` (`core/dependencies.py:67-114`) declarado por rota.\n")

    add("## 3. Tabela completa\n")
    add("| # | Método | Path | Autenticação | Papéis com acesso | Escopo | Recebe ID? | Tipo | CSRF | C1 banco/isolamento | C2 UI×servidor | C3 IDOR |")
    add("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(routes, 1):
        c = classify(r)
        m, p = c["m"], c["p"]
        ids = r["params"]["path"]
        indirect = INDIRECT_IDS.get((m, p))
        id_txt = ", ".join([f"path.{x}" for x in ids] + ([indirect] if indirect else [])) or "não"
        last = p.rstrip("/").split("/")[-1]
        if (m, p) in PUBLIC_BY_DESIGN:
            kind = "utilitário (health/auth)"
        elif p.startswith("/api/v1/exports") and m == "POST" or "/download" in p:
            kind = "exportação/download"
        elif p in ("/api/v1/dashboard/summary", "/api/v1/search", "/api/v1/metrics") or "/reports/" in p or "/audit-events" in p or "occupancy" in p:
            kind = "agregação/relatório"
        elif m == "GET" and not last.startswith("{"):
            kind = "listagem"
        elif m == "GET":
            kind = "leitura por ID"
        else:
            kind = "mutação" if m in ("POST", "PATCH", "DELETE", "PUT") else m
        scope = "n/a" if (m, p) in PUBLIC_BY_DESIGN else "global (single-tenant)"
        v1, v2, v3 = verdicts(c, r)
        csrf = "sim" if c["csrf"] else ("—" if m == "GET" else "**não**")
        add(f"| {i} | {m} | `{p}` | {c['auth']} | {c['roles']} | {scope} | {id_txt} | {kind} | {csrf} | {v1} | {v2} | {v3} |")

    add("\n## 4. Matriz de permissões (fonte: `backend/app/core/permissions.py`) × frontend (`frontend/src/lib/permissions/rbac.ts`)\n")
    add("| Permissão | viewer | technician | engineer | admin |")
    add("|---|---|---|---|---|")
    allperms = sorted({x for v in ROLE_PERMISSIONS_STR.values() for x in v})
    for pm in allperms:
        add(f"| `{pm}` | " + " | ".join("✔" if pm in ROLE_PERMISSIONS_STR[ro] else "" for ro in ROLE_ORDER) + " |")
    add("\nPermissões **definidas mas nunca exigidas por nenhuma rota** (`grep require_permission`): "
        + ", ".join(f"`{x}`" for x in allperms if x not in {p for r in routes for d in r['deps'] if d[0] == 'perm' for p in [d[1]]}) + ".")
    add("`telemetry:write` existe só no frontend (`rbac.ts:12`), não no servidor.\n")

    add("## 5. Gates de papel do frontend cruzados com o servidor (P0 item 6)\n")
    add("| Gate no frontend | Local | Endpoint correspondente | Servidor valida? |")
    add("|---|---|---|---|")
    add("| `AuthGuard` (somente sessão; `requiredPermission`/`requiredRole` **nunca usados**) | `frontend/src/app/(app)/layout.tsx:6` | todos | sim — `get_current_user` / `require_permission` em 89 handlers; 9 handlers sem auth (achados) |")
    add("| `isAdmin = user?.role === \"admin\"` (aviso de LGPD na camada `customers`) | `frontend/src/features/imports_exports/components/export-wizard.tsx:29` | `POST /api/v1/exports` | **sim** — `exports/service.py:62` bloqueia camada `customers` se `role != admin` |")
    add("| `PermissionGate` / `hasPermission()` (componentes existem) | `components/auth/permission-gate.tsx`, `features/auth/auth-context.tsx:82` | — | **não são usados por nenhuma página/feature** (`grep PermissionGate` fora de `components/auth/` → 0) |")
    add("| Sidebar: `permission?: string` no tipo de item | `frontend/src/lib/navigation.ts:32` | — | campo declarado mas nenhum item o preenche/consome (`sidebar.tsx` não filtra por permissão) |")

    (OUT_DIR / "inventario-rotas.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {total_handlers} handlers / {total_pairs} pares -> inventario-rotas.md")


if __name__ == "__main__":
    main()
