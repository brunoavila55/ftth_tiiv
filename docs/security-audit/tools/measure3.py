import os, sys
URL = os.environ["DATABASE_URL"]; assert "127.0.0.1:55432/audit" in URL
sys.path.insert(0, "/home/bruno/projects/ftth_tiiv/backend")
from fastapi.testclient import TestClient
from app.main import app
cl = TestClient(app, raise_server_exceptions=False)
tok = "csrf-token-attacker-chosen"
def login(origin):
    cl.cookies.clear()
    cl.cookies.set("ftth_csrf_token", tok)
    r = cl.post("/api/v1/auth/login", json={"email":"nobody@example.com","password":"x"}, headers={"Origin": origin, "X-CSRF-Token": tok})
    return r.status_code, r.json().get("code")
for o in ["http://localhost:3000", "https://evil.example", "http://localhost:3000.evil.example", "http://127.0.0.1:3000.attacker.test"]:
    print(f"Origin={o!r:45} -> {login(o)}")
# Settings: METRICS_TOKEN (compose) vs METRICS_SECRET_TOKEN (config)
os.environ["METRICS_TOKEN"] = "abcd-compose-value-1234"
from app.core.config import Settings
s = Settings()
print("compose METRICS_TOKEN definido; Settings.METRICS_SECRET_TOKEN começa com:", s.METRICS_SECRET_TOKEN[:4] + "…", "| igual ao default do código:", s.METRICS_SECRET_TOKEN == Settings.model_fields["METRICS_SECRET_TOKEN"].default)
os.environ["ENVIRONMENT"]="production"
s2 = Settings()
print("ENVIRONMENT=production aceita SECRET_KEY default?", s2.SECRET_KEY[:4]+"…", "is_production:", s2.is_production)
# Pillow
from PIL import Image
print("DecompressionBombError bases:", [b.__name__ for b in Image.DecompressionBombError.__mro__], "| MAX_IMAGE_PIXELS:", Image.MAX_IMAGE_PIXELS)
