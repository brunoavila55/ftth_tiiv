import os, sys, time, json
URL = os.environ["DATABASE_URL"]; assert "127.0.0.1:55432/audit" in URL
sys.path.insert(0, "/home/bruno/projects/ftth_tiiv/backend")
from datetime import datetime, timedelta, UTC
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_engine
from app.core.security import hash_password, generate_session_token
from app.modules.identity.models import User, UserSession

eng = create_engine(URL)
with eng.connect() as c:
    rows = c.execute(text("EXPLAIN (ANALYZE, FORMAT TEXT) select * from terminals where entity_type='port' and entity_id='00000000-0000-0000-0000-000000000001'")).fetchall()
    print("### terminals(entity_type,entity_id) lookup:"); [print(" ", r[0]) for r in rows if any(k in r[0] for k in ("Scan","Execution","Rows Removed"))]
    seg = c.execute(text("select id from cable_segments limit 1")).scalar()

import uuid as _u
raw, th = generate_session_token()
with Session(eng) as s:
    u = User(email=f"audit-{_u.uuid4().hex[:6]}@local.test", name="audit", password_hash=hash_password("x"*12), role="viewer", is_active=True, version=1)
    s.add(u); s.flush()
    now = datetime.now(UTC)
    s.add(UserSession(user_id=u.id, token_hash=th, created_at=now, last_activity_at=now, expires_at=now+timedelta(days=1), is_revoked=False))
    s.commit()

stmts = []
@event.listens_for(get_engine(), "before_cursor_execute")
def _c(conn, cursor, statement, parameters, context, executemany): stmts.append(statement)
cl = TestClient(app, raise_server_exceptions=False)
H = {"Authorization": f"Bearer {raw}"}
r = cl.get("/api/v1/auth/me", headers=H); print("\n/auth/me as viewer:", r.status_code, r.json().get("role"))
# viewer lê clientes (PII) ?
r = cl.get("/api/v1/customers", headers=H); print("### VIEWER GET /customers:", r.status_code, [ (k, ("<%d chars>"%len(str(v)) if v else v)) for k,v in (r.json()["items"][0].items() if r.status_code==200 and r.json()["items"] else [])][:8])
r = cl.get("/api/v1/attachments", headers=H); print("### VIEWER GET /attachments:", r.status_code)
r = cl.get("/api/v1/audit-events", headers=H); print("### VIEWER GET /audit-events:", r.status_code)
r = cl.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000", headers=H); print("### VIEWER GET /jobs/<uuid>:", r.status_code)
r = cl.get("/api/v1/customers/not-a-uuid", headers=H); print("### GET /customers/not-a-uuid:", r.status_code, r.headers.get("content-type"))
r = cl.get("/api/v1/metrics", headers={"X-Metrics-Token": __import__("app.core.config", fromlist=["Settings"]).Settings.model_fields["METRICS_SECRET_TOKEN"].default}); print("### GET /metrics com token default público:", r.status_code)
for i in range(2):
    stmts.clear(); t0=time.perf_counter()
    r = cl.post("/api/v1/topology/impact", headers={**H}, json={"cable_segment_ids":[str(seg)], "expected_topology_revision": 1})
    print(f"### VIEWER POST /topology/impact (1 cliente, 1 vínculo): status={r.status_code} {(time.perf_counter()-t0)*1000:.0f} ms, {len(stmts)} SQL")
    if r.status_code != 200: print(r.text[:300])
# cardinalidade de métricas: paths inexistentes sem auth
from app.core.metrics import metrics_collector
n0 = len(metrics_collector._http_requests)
for i in range(300): cl.get(f"/scan-{i}-x")
print(f"### métricas: chaves _http_requests antes={n0} depois de 300 GETs a paths 404 distintos={len(metrics_collector._http_requests)}")
