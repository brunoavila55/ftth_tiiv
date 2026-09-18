import os, sys, time, threading, statistics
URL = os.environ["DATABASE_URL"]; assert "127.0.0.1:55432/audit" in URL
sys.path.insert(0, "/home/bruno/projects/ftth_tiiv/backend")
from fastapi.testclient import TestClient
from app.main import app
import logging; logging.disable(logging.CRITICAL)
N = 20
lat = []; lock = threading.Lock()
def one():
    with TestClient(app, raise_server_exceptions=False) as c:
        t0 = time.perf_counter(); r = c.get("/api/v1/dashboard/summary"); dt = time.perf_counter()-t0
        with lock: lat.append((r.status_code, dt))
ready = []
def probe():
    with TestClient(app, raise_server_exceptions=False) as c:
        for _ in range(6):
            t0 = time.perf_counter(); r = c.get("/health/ready"); ready.append((r.status_code, time.perf_counter()-t0)); time.sleep(0.5)
with TestClient(app, raise_server_exceptions=False) as c:
    t0 = time.perf_counter(); c.get("/health/ready"); base = time.perf_counter()-t0
    t0 = time.perf_counter(); c.get("/api/v1/dashboard/summary"); seq = time.perf_counter()-t0
print(f"baseline /health/ready={base*1000:.0f} ms; dashboard sequencial={seq*1000:.0f} ms")
ths = [threading.Thread(target=one) for _ in range(N)] + [threading.Thread(target=probe)]
t0 = time.perf_counter()
[t.start() for t in ths]; [t.join() for t in ths]
wall = time.perf_counter()-t0
ds = sorted(d for _, d in lat)
print(f"{N} dashboards concorrentes SEM auth: wall={wall:.1f}s (sequencial teórico {N*seq:.1f}s), p50={statistics.median(ds):.1f}s, max={ds[-1]:.1f}s, status={sorted(set(s for s,_ in lat))}")
print("/health/ready durante a carga (ms):", [round(d*1000) for _, d in ready], "status:", sorted(set(s for s,_ in ready)))
