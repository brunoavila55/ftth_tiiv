"""R11 (SEC-13 / SEC-14): exportações auditadas, download revalidado, expiração e erros de job."""

import io
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.audit.models import AuditEvent
from app.modules.customers.models import Customer
from app.modules.imports.models import AsyncJob
from app.modules.inventory.models import Site
from app.modules.jobs.service import clean_expired_previews_and_exports, process_next_job
from tests.conftest import create_test_user, login_test_client


def login(client: TestClient, db: Session, role: str) -> tuple[str, str]:
    email = f"{role}_{uuid.uuid4().hex[:6]}@provedor.com.br"
    user = create_test_user(db, email, role)
    return str(user.id), login_test_client(client, email)


def request_export(client: TestClient, csrf: str, layers: list[str], fmt: str = "geojson") -> str:
    resp = client.post(
        "/api/v1/exports",
        json={"format": fmt, "layers": layers},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
    return str(resp.json()["job_id"])


def events(db: Session, action: str) -> list[AuditEvent]:
    db.expire_all()
    return list(db.scalars(select(AuditEvent).where(AuditEvent.action == action)).all())


# ---------------------------------------------------------------------------------------------
# SEC-13 — auditoria da exportação
# ---------------------------------------------------------------------------------------------


def test_export_request_and_download_are_audited(client: TestClient, db_session: Session) -> None:
    admin_id, csrf = login(client, db_session, "admin")
    job_id = request_export(client, csrf, ["sites", "customers"], "csv")

    (requested,) = events(db_session, "export_requested")
    assert str(requested.actor_id) == admin_id
    assert str(requested.entity_id) == job_id
    assert requested.changes["format"] == "csv"
    assert requested.changes["layers"] == ["sites", "customers"]
    assert requested.request_id

    job = db_session.get(AsyncJob, uuid.UUID(job_id))
    assert job is not None and job.payload is not None
    assert job.payload["requested_by"] == admin_id  # quem pediu vai no payload do job
    assert job.payload["layers"] == ["sites", "customers"]
    # exatamente 1 evento para a chamada (o genérico não duplica o explícito)
    assert db_session.scalar(select(func.count(AuditEvent.id))) == 2  # login + export_requested

    assert process_next_job(db_session) is True
    assert events(db_session, "export_downloaded") == []
    resp = client.get(f"/api/v1/exports/{job_id}/download")
    assert resp.status_code == status.HTTP_200_OK
    (downloaded,) = events(db_session, "export_downloaded")
    assert str(downloaded.actor_id) == admin_id and str(downloaded.entity_id) == job_id
    assert downloaded.changes["layers"] == ["sites", "customers"]


def test_customer_layer_export_download_requires_admin(
    client: TestClient, db_session: Session
) -> None:
    _, admin_csrf = login(client, db_session, "admin")
    db_session.add(Customer(code="CLI-EXP", name="Fulano", phone="11999990000", version=1))
    db_session.commit()
    job_id = request_export(client, admin_csrf, ["customers"])
    assert process_next_job(db_session) is True
    assert client.get(f"/api/v1/exports/{job_id}/download").status_code == status.HTTP_200_OK

    # engineer tem exports:read, conhece o job_id, mas NÃO é admin
    engineer_client = TestClient(client.app, raise_server_exceptions=False)
    login(engineer_client, db_session, "engineer")
    resp = engineer_client.get(f"/api/v1/exports/{job_id}/download")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "Fulano" not in resp.text
    # exportação sem a camada de clientes continua baixável por engineer
    admin2 = TestClient(client.app, raise_server_exceptions=False)
    _, csrf2 = login(admin2, db_session, "admin")
    plain_job = request_export(admin2, csrf2, ["sites"])
    assert process_next_job(db_session) is True
    assert engineer_client.get(f"/api/v1/exports/{plain_job}/download").status_code == 200


def test_expired_export_files_are_removed_and_download_returns_410(
    client: TestClient, db_session: Session
) -> None:
    _, csrf = login(client, db_session, "admin")
    db_session.add(
        Site(code="S-TTL", name="Site", kind="pop", status="installed", location="POINT(-46 -23)")
    )
    db_session.commit()
    job_id = request_export(client, csrf, ["sites"])
    assert process_next_job(db_session) is True
    job = db_session.get(AsyncJob, uuid.UUID(job_id))
    assert job is not None and job.result_path and Path(job.result_path).exists()
    file_path = Path(job.result_path)

    ttl_days = get_settings().EXPORT_TTL_DAYS
    assert ttl_days == 7  # padrão confirmado com o operador (sugestão do roteiro)

    # dentro do prazo: o worker não remove
    job.finished_at = datetime.now(UTC) - timedelta(days=ttl_days - 1)
    db_session.commit()
    assert clean_expired_previews_and_exports(db_session)["expired_exports"] == 0
    assert file_path.exists()

    # vencido: o download já responde 410 mesmo antes do worker limpar...
    job.finished_at = datetime.now(UTC) - timedelta(days=ttl_days + 1)
    db_session.commit()
    assert client.get(f"/api/v1/exports/{job_id}/download").status_code == status.HTTP_410_GONE
    assert file_path.exists()
    # ...e o worker remove o arquivo
    assert clean_expired_previews_and_exports(db_session)["expired_exports"] == 1
    assert not file_path.exists()
    assert client.get(f"/api/v1/exports/{job_id}/download").status_code == status.HTTP_410_GONE
    # idempotente
    assert clean_expired_previews_and_exports(db_session)["expired_exports"] == 0


def test_export_ttl_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXPORT_TTL_DAYS", "2")
    get_settings.cache_clear()
    assert get_settings().EXPORT_TTL_DAYS == 2


# ---------------------------------------------------------------------------------------------
# SEC-14 — erros de job sanitizados e leitura restrita por tipo
# ---------------------------------------------------------------------------------------------


def make_geojson(code: str) -> bytes:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-46.9, -23.9]},
                    "properties": {
                        "code": code,
                        "name": "POP",
                        "type": "pop",
                        "entity_type": "site",
                    },
                }
            ],
        }
    ).encode()


def test_job_error_does_not_leak_sql_tables_or_paths(
    client: TestClient, db_session: Session
) -> None:
    _, csrf = login(client, db_session, "admin")
    preview = client.post(
        "/api/v1/imports/preview",
        files={
            "file": ("rede.geojson", io.BytesIO(make_geojson("POP-RACE")), "application/geo+json")
        },
        headers={"X-CSRF-Token": csrf},
    ).json()
    # depois da prévia, outro operador cria o mesmo código: o INSERT do commit viola a unicidade
    db_session.add(
        Site(
            code="POP-RACE", name="Outro", kind="pop", status="installed", location="POINT(-46 -23)"
        )
    )
    db_session.commit()

    commit = client.post(
        f"/api/v1/imports/{preview['import_id']}/commit",
        json={"import_id": preview["import_id"], "file_hash": preview["file_hash"]},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": f"idem-{uuid.uuid4()}"},
    )
    assert commit.status_code == status.HTTP_202_ACCEPTED, commit.text
    job_id = commit.json()["job_id"]
    assert process_next_job(db_session) is True

    resp = client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "failed"
    text = json.dumps(body).lower()
    for leaked in (
        "duplicate",
        "unique",
        "constraint",
        "insert",
        "sites",
        "psycopg",
        "sqlalchemy",
        "detail:",
        "/storage",
        os.sep + "imports",
        "key (",
    ):
        assert leaked not in text, f"{leaked!r} vazou em {body}"
    assert body["error_message"]  # mas há uma mensagem útil e genérica


def test_missing_import_file_message_has_no_server_path(
    client: TestClient, db_session: Session
) -> None:
    job = AsyncJob(
        type="import_commit",
        status="queued",
        idempotency_key="path-leak-1",
        payload={"file_storage_path": "/srv/segredo/imports/arquivo.geojson", "format": "geojson"},
    )
    db_session.add(job)
    db_session.commit()
    assert process_next_job(db_session) is True
    db_session.refresh(job)
    assert job.status == "failed"
    assert "/srv" not in (job.error_message or "") and "segredo" not in (job.error_message or "")


@pytest.mark.parametrize(
    ("role", "job_type", "expected"),
    [
        ("viewer", "export_geojson", 403),
        ("viewer", "import_commit", 403),
        ("technician", "export_csv", 403),
        ("technician", "import_commit", 403),
        ("engineer", "export_csv", 200),
        ("engineer", "import_commit", 200),
        ("admin", "export_kml", 200),
        ("admin", "import_commit", 200),
    ],
)
def test_job_status_requires_permission_by_job_type(
    client: TestClient, db_session: Session, role: str, job_type: str, expected: int
) -> None:
    job = AsyncJob(type=job_type, status="queued", idempotency_key=f"k-{uuid.uuid4()}")
    db_session.add(job)
    db_session.commit()
    login(client, db_session, role)
    assert client.get(f"/api/v1/jobs/{job.id}").status_code == expected
