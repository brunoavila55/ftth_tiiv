"""Medições PERF em Postgres DESCARTÁVEL (127.0.0.1:55432). Aborta se DATABASE_URL não for o descartável."""
import os, sys, time, json, statistics
URL = os.environ["DATABASE_URL"]
assert "127.0.0.1:55432/audit" in URL, "URL inesperada: abortando por segurança"
sys.path.insert(0, "/home/bruno/projects/ftth_tiiv/backend")
from sqlalchemy import create_engine, text, event
from fastapi.testclient import TestClient

eng = create_engine(URL)
out = {}
with eng.connect() as c:
    tables = ["users","sites","structures","devices","ports","cables","cable_segments","fibers","fiber_segments","terminals","connections","customers","service_links","audit_events","login_attempts","user_sessions"]
    out["rows"] = {t: c.execute(text(f"select count(*) from {t}")).scalar() for t in tables}
    print("ROWS", json.dumps(out["rows"]))
    def explain(label, sql, params=None):
        rows = c.execute(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + sql), params or {}).fetchall()
        txt = "\n".join(r[0] for r in rows)
        keep = [l for l in txt.splitlines() if any(k in l for k in ("Scan","Execution Time","Planning Time","Sort","Rows Removed"))]
        print(f"\n### {label}"); print("\n".join(keep[:8]))
        out.setdefault("explain", {})[label] = keep[:8]
    explain("search devices ILIKE %x% (code/model/serial)", "select * from devices where status<>'retired' and (code ilike '%OLT%' or model ilike '%OLT%' or serial_number ilike '%OLT%') limit 20")
    explain("search structures ILIKE %x% (code)", "select * from structures where status<>'retired' and code ilike '%9999%' limit 20")
    explain("search ports.notes ILIKE (dashboard/inconsistencies)", "select count(*) from ports where notes ilike '%danificad%' or notes ilike '%defeito%' or notes ilike '%quebrad%'")
    pid = c.execute(text("select entity_id from terminals where entity_type='port' and entity_id is not null limit 1 offset 5000")).scalar()
    print("sample port entity_id:", pid)
    if pid:
        explain("terminals WHERE entity_type='port' AND entity_id=:id", "select * from terminals where entity_type='port' and entity_id=:id", {"id": pid})
    explain("structures ORDER BY created_at DESC OFFSET 9000 (list, sem índice em created_at)", "select * from structures order by created_at desc, id offset 9000 limit 50")
    explain("count(*) structures", "select count(structures.id) from structures")

# --- N+1 do dashboard (endpoint SEM autenticação)
from app.main import app
from app.db.session import get_engine
stmts = []
ge = get_engine()
@event.listens_for(ge, "before_cursor_execute")
def _c(conn, cursor, statement, parameters, context, executemany):
    stmts.append(statement)
cl = TestClient(app)
for i in range(3):
    stmts.clear(); t0 = time.perf_counter()
    r = cl.get("/api/v1/dashboard/summary")
    dt = time.perf_counter() - t0
    print(f"\n### GET /api/v1/dashboard/summary (SEM auth) run{i+1}: status={r.status_code} {dt*1000:.0f} ms, {len(stmts)} SQL statements")
    out.setdefault("dashboard", []).append({"status": r.status_code, "ms": round(dt*1000), "sql": len(stmts)})
stmts.clear(); t0=time.perf_counter()
r = cl.get("/api/v1/search", params={"q": "OLT"}); dt=time.perf_counter()-t0
print(f"### GET /api/v1/search?q=OLT (SEM auth): status={r.status_code} {dt*1000:.0f} ms, {len(stmts)} SQL; groups={[g['entity_type'] for g in r.json().get('groups',[])]}")
out["search_anon"] = {"status": r.status_code, "ms": round(dt*1000), "sql": len(stmts), "groups": [g['entity_type'] for g in r.json().get('groups',[])]}
json.dump(out, open("/tmp/audit-env/measure_out.json","w"), indent=1, default=str)
