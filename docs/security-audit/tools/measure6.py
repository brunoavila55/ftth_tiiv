import os, sys, time, resource
URL = os.environ["DATABASE_URL"]; assert "127.0.0.1:55432/audit" in URL
sys.path.insert(0, "/home/bruno/projects/ftth_tiiv/backend")
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.modules.cables.service import create_cable
from app.schemas.cables import CableCreate
import logging; logging.disable(logging.CRITICAL)
eng = create_engine(URL)
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
for n in (10_000, 40_000):
    with Session(eng, expire_on_commit=False) as s:
        base = rss(); t0 = time.perf_counter()
        create_cable(s, CableCreate(code=f"AUD-{n}", model="X", fiber_count=n, tube_count=1))
        dt = time.perf_counter()-t0
        print(f"fiber_count={n:>6}: {dt:5.1f}s, RSS pico {rss():.0f} MiB (+{rss()-base:.0f} MiB) — payload JSON tem ~60 bytes")
