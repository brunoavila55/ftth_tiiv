"""Enumera TODAS as rotas do app FastAPI via introspeção (sem executar handlers)."""
import inspect, json, sys, os
sys.path.insert(0, "/home/bruno/projects/ftth_tiiv/backend")
os.environ.setdefault("ENVIRONMENT", "test")
from fastapi.routing import APIRoute
from app.main import app

def walk(dep, out):
    for sd in dep.dependencies:
        c = sd.call
        name = getattr(c, "__name__", str(c))
        if name == "_permission_dependency":
            perm = None
            for cell in (c.__closure__ or []):
                v = cell.cell_contents
                if isinstance(v, str): perm = v
            out.append(("perm", perm))
        else:
            out.append(("dep", name))
        walk(sd, out)

rows = []
ctxs = []
for r in app.routes:
    if type(r).__name__ == "_IncludedRouter":
        ctxs.extend(r.effective_route_contexts())
    elif isinstance(r, APIRoute):
        ctxs.append(r)
    else:
        rows.append({"kind": type(r).__name__, "path": getattr(r, "path", None)})

for r in ctxs:
    path = getattr(r, "path", None) or r.path_format
    deps = []
    walk(r.dependant, deps)
    ep = r.endpoint
    src = inspect.getsourcefile(ep)
    line = inspect.getsourcelines(ep)[1]
    params = {
        "path": [p.name for p in r.dependant.path_params],
        "query": [p.name for p in r.dependant.query_params],
        "header": [p.name for p in r.dependant.header_params],
        "body": [p.name for p in r.dependant.body_params],
    }
    rows.append({
        "methods": sorted(r.methods), "path": path, "name": r.name,
        "file": os.path.relpath(src, "/home/bruno/projects/ftth_tiiv"), "line": line,
        "async": inspect.iscoroutinefunction(ep),
        "deps": deps, "params": params,
    })
json.dump(rows, open("/tmp/audit-env/routes.json", "w"), indent=1)
api = [r for r in rows if "methods" in r]
print("total handlers:", len(api), "| total (método,path):", sum(len(r["methods"]) for r in api), "| non-API routes:", len(rows)-len(api))
for r in rows:
    if "methods" not in r: print("NON-API:", r)
