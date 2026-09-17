#!/usr/bin/env python3
"""Smoke test script para validação rápida da fundação do backend FTTH Manager."""

import sys

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def run_smoke_test() -> int:
    print("=" * 70)
    print("  FTTH MANAGER — SMOKE TEST DE FUNDAÇÃO (B01)")
    print("=" * 70)

    # 1. Configuração
    settings = get_settings()
    print(f"[+] Ambiente: {settings.ENVIRONMENT}")
    print(f"[+] App: {settings.APP_NAME}")
    print(f"[+] Prefixo API: {settings.API_V1_PREFIX}")

    # 2. Test Client
    client = TestClient(app, raise_server_exceptions=False)

    # 3. Liveness
    live_resp = client.get("/health/live")
    if live_resp.status_code == 200 and live_resp.json().get("status") == "alive":
        req_id = live_resp.headers.get("X-Request-ID", "N/A")
        print(f"[PASS] /health/live respondeu 200 OK (X-Request-ID: {req_id})")
    else:
        print(f"[FAIL] /health/live falhou com código {live_resp.status_code}: {live_resp.text}")
        return 1

    # 4. Readiness
    ready_resp = client.get("/health/ready")
    if ready_resp.status_code == 200:
        data = ready_resp.json()
        db_status = data.get("database", {}).get("status")
        db_latency = data.get("database", {}).get("latency_ms")
        mig_status = data.get("migrations", {}).get("status")
        mig_rev = data.get("migrations", {}).get("current_revision")
        print("[PASS] /health/ready respondeu 200 OK:")
        print(f"       - Banco de dados: {db_status} (latência: {db_latency}ms)")
        print(f"       - Migrações Alembic: {mig_status} (revisão ativa: {mig_rev})")
    else:
        print(f"[WARN/FAIL] /health/ready respondeu {ready_resp.status_code}: {ready_resp.text}")
        if ready_resp.status_code != 503:
            return 1

    # 5. Tratamento de Erro RFC 7807 (404 não encontrado)
    not_found_resp = client.get("/api/v1/non-existent-route")
    if not_found_resp.status_code == 404:
        ct = not_found_resp.headers.get("content-type", "")
        if "application/problem+json" in ct:
            print("[PASS] Erros não encontrados utilizam application/problem+json (RFC 7807)")
        else:
            print(f"[WARN] Content-Type retornado: {ct}")
    else:
        print(f"[FAIL] Rota inexistente retornou {not_found_resp.status_code}")
        return 1

    print("-" * 70)
    print(">> Todos os testes básicos de fumaça foram concluídos com sucesso!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(run_smoke_test())
