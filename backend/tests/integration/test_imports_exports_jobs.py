"""Testes de integração para Importação, Exportação e Fila Assíncrona de Jobs (B14).

Cobre:
- Ciclo de vida de importação GeoJSON: preview sem alteração da rede e commit atômico.
- Idempotência: requisição com a mesma Idempotency-Key não duplica jobs ou entidades.
- Detecção e bloqueio estrito de colisões com elementos já existentes no banco de dados.
- Neutralização e defesa contra injeção de fórmulas de planilha em CSV (importação e exportação).
- Exportações em GeoJSON, KML e CSV com download autenticado.
- Proteção de privacidade (LGPD) exigindo permissões elevadas para exportar dados de clientes.
- Cancelamento de job pelo operador.
- Recuperação de job após crash/expiração de lease do worker.
"""

import io
import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.gis.helpers import point_geometry_to_wkb
from app.modules.identity.models import User
from app.modules.imports.models import AsyncJob
from app.modules.inventory.models import Site, Structure
from app.modules.jobs.service import claim_next_job, process_next_job
from app.schemas.common import UserRole
from app.schemas.geojson import PointGeometry


def auth_client_login(client: TestClient, email: str, password: str = "AdminPass123!") -> str:
    csrf_resp = client.get("/api/v1/auth/csrf")
    assert csrf_resp.status_code == status.HTTP_200_OK
    initial_token = csrf_resp.json()["csrf_token"]

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": initial_token},
    )
    assert login_resp.status_code == status.HTTP_200_OK
    rotated_token = client.cookies.get("ftth_csrf_token")
    assert rotated_token is not None
    return str(rotated_token)


def create_user(db_session: Session, email: str, role: str) -> User:
    user = User(
        email=email,
        name=f"User {role}",
        password_hash=hash_password("AdminPass123!"),
        role=role,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_import_geojson_preview_and_commit_lifecycle(
    client: TestClient, db_session: Session
) -> None:
    admin = create_user(db_session, "admin_import@provedor.com.br", UserRole.ADMIN.value)
    csrf_token = auth_client_login(client, admin.email)

    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
                "properties": {
                    "code": "POP-CENTRO",
                    "name": "POP Central",
                    "type": "pop",
                    "entity_type": "site",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-46.6340, -23.5510]},
                "properties": {
                    "code": "POSTE-01",
                    "name": "Poste de Acesso 01",
                    "type": "pole",
                    "entity_type": "structure",
                },
            },
        ],
    }

    file_bytes = json.dumps(geojson_data).encode("utf-8")

    # 1. Preview da importação
    preview_resp = client.post(
        "/api/v1/imports/preview",
        files={"file": ("rede.geojson", io.BytesIO(file_bytes), "application/geo+json")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert preview_resp.status_code == status.HTTP_200_OK
    p_data = preview_resp.json()
    import_id = p_data["import_id"]
    file_hash = p_data["file_hash"]

    assert p_data["total_records"] == 2
    assert p_data["valid_records"] == 2
    assert p_data["error_records"] == 0
    assert p_data["collision_records"] == 0

    # 2. Garantia de que a rede NÃO foi alterada pela prévia
    sites_count = db_session.scalar(select(Site).where(Site.code == "POP-CENTRO"))
    assert sites_count is None

    # 3. Consultar prévia por ID
    get_prev_resp = client.get(f"/api/v1/imports/{import_id}")
    assert get_prev_resp.status_code == status.HTTP_200_OK
    assert get_prev_resp.json()["import_id"] == import_id

    # 4. Commit da importação com Idempotency-Key
    idemp_key = f"idemp-{uuid.uuid4()}"
    commit_resp = client.post(
        f"/api/v1/imports/{import_id}/commit",
        json={"import_id": import_id, "file_hash": file_hash},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idemp_key},
    )
    assert commit_resp.status_code == status.HTTP_202_ACCEPTED
    job_id = commit_resp.json()["job_id"]

    # 5. Executar worker de processamento do job
    worked = process_next_job(db_session, worker_id="test-worker")
    assert worked is True

    # 6. Validar status do job
    job_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert job_resp.status_code == status.HTTP_200_OK
    assert job_resp.json()["status"] == "succeeded"
    assert job_resp.json()["progress_percentage"] == 100

    # 7. Validar persistência na rede física
    site = db_session.scalar(select(Site).where(Site.code == "POP-CENTRO"))
    assert site is not None
    assert site.name == "POP Central"

    struct = db_session.scalar(select(Structure).where(Structure.code == "POSTE-01"))
    assert struct is not None
    assert struct.kind == "pole"


def test_import_idempotency_key_does_not_duplicate(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin_idemp@provedor.com.br", UserRole.ADMIN.value)
    csrf_token = auth_client_login(client, admin.email)

    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
                "properties": {"code": "POP-IDEMP", "name": "POP Idemp", "type": "pop"},
            }
        ],
    }
    file_bytes = json.dumps(geojson_data).encode("utf-8")

    preview_resp = client.post(
        "/api/v1/imports/preview",
        files={"file": ("rede.geojson", io.BytesIO(file_bytes), "application/geo+json")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert preview_resp.status_code == status.HTTP_200_OK
    import_id = preview_resp.json()["import_id"]
    file_hash = preview_resp.json()["file_hash"]

    idemp_key = "idemp-unique-token-12345"

    # Primeira chamada
    resp1 = client.post(
        f"/api/v1/imports/{import_id}/commit",
        json={"import_id": import_id, "file_hash": file_hash},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idemp_key},
    )
    assert resp1.status_code == status.HTTP_202_ACCEPTED
    job1_id = resp1.json()["job_id"]

    # Segunda chamada com a mesma chave (retry de rede)
    resp2 = client.post(
        f"/api/v1/imports/{import_id}/commit",
        json={"import_id": import_id, "file_hash": file_hash},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idemp_key},
    )
    assert resp2.status_code == status.HTTP_202_ACCEPTED
    job2_id = resp2.json()["job_id"]

    # Deve retornar o mesmo job sem duplicar
    assert job1_id == job2_id

    # Garantir que só há 1 job no banco
    jobs_count = db_session.scalars(
        select(AsyncJob).where(AsyncJob.idempotency_key == idemp_key)
    ).all()
    assert len(jobs_count) == 1


def test_import_collision_detection_and_rejection(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin_coll@provedor.com.br", UserRole.ADMIN.value)
    csrf_token = auth_client_login(client, admin.email)

    # Pré-inserir elemento com código POP-EXISTING
    pre_site = Site(
        code="POP-EXISTING",
        name="POP Já Cadastrado",
        kind="pop",
        status="installed",
        location=point_geometry_to_wkb(PointGeometry(coordinates=[-46.6333, -23.5505])),
        version=1,
    )
    db_session.add(pre_site)
    db_session.commit()

    # Arquivo com o mesmo código
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
                "properties": {"code": "POP-EXISTING", "name": "POP Duplicado", "type": "pop"},
            }
        ],
    }
    file_bytes = json.dumps(geojson_data).encode("utf-8")

    preview_resp = client.post(
        "/api/v1/imports/preview",
        files={"file": ("rede.geojson", io.BytesIO(file_bytes), "application/geo+json")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert preview_resp.status_code == status.HTTP_200_OK
    p_data = preview_resp.json()
    assert p_data["collision_records"] == 1
    assert p_data["valid_records"] == 0
    assert p_data["sample_preview"][0]["validation_status"] == "collision"

    # Tentativa de commit deve ser bloqueada pelo modo All-or-Nothing
    commit_resp = client.post(
        f"/api/v1/imports/{p_data['import_id']}/commit",
        json={"import_id": p_data["import_id"], "file_hash": p_data["file_hash"]},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": f"idemp-{uuid.uuid4()}"},
    )
    assert commit_resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "colisões" in commit_resp.json()["detail"]


def test_import_csv_and_formula_injection_defense(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin_csv@provedor.com.br", UserRole.ADMIN.value)
    csrf_token = auth_client_login(client, admin.email)

    # CSV com fórmula maliciosa '=cmd'
    csv_content = (
        b"code,name,entity_type,latitude,longitude\n"
        b"SITE-01,Site Normal,site,-23.5505,-46.6333\n"
        b"=cmd|' /C calc'!A0,Site Perigoso,site,-23.5510,-46.6340\n"
    )

    preview_resp = client.post(
        "/api/v1/imports/preview",
        files={"file": ("planilha.csv", io.BytesIO(csv_content), "text/csv")},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert preview_resp.status_code == status.HTTP_200_OK
    p_data = preview_resp.json()

    assert p_data["total_records"] == 2
    assert p_data["error_records"] == 1
    assert p_data["valid_records"] == 1

    # Verificar diagnóstico da linha maliciosa
    error_item = next(it for it in p_data["sample_preview"] if it["validation_status"] == "error")
    assert "injeção de fórmula" in error_item["message"].lower()


def test_export_geojson_and_csv_neutralization(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin_exp@provedor.com.br", UserRole.ADMIN.value)
    csrf_token = auth_client_login(client, admin.email)

    # Inserir elemento cujo código começa com caracter de fórmula
    site = Site(
        code="+SITE-FORMULA",
        name="Site Formula",
        kind="pop",
        status="installed",
        location=point_geometry_to_wkb(PointGeometry(coordinates=[-46.6333, -23.5505])),
        version=1,
    )
    db_session.add(site)
    db_session.commit()

    # 1. Export CSV
    exp_csv_resp = client.post(
        "/api/v1/exports",
        json={"format": "csv", "layers": ["sites"]},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert exp_csv_resp.status_code == status.HTTP_202_ACCEPTED
    csv_job_id = exp_csv_resp.json()["job_id"]

    # Processar job no worker
    assert process_next_job(db_session) is True

    # Download CSV
    dl_resp = client.get(f"/api/v1/exports/{csv_job_id}/download")
    assert dl_resp.status_code == status.HTTP_200_OK
    csv_text = dl_resp.text
    # Deve conter '+SITE-FORMULA neutralizado com apóstrofo
    assert "'+SITE-FORMULA" in csv_text

    # 2. Export GeoJSON
    exp_geo_resp = client.post(
        "/api/v1/exports",
        json={"format": "geojson", "layers": ["sites"]},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert exp_geo_resp.status_code == status.HTTP_202_ACCEPTED
    geo_job_id = exp_geo_resp.json()["job_id"]

    assert process_next_job(db_session) is True

    dl_geo_resp = client.get(f"/api/v1/exports/{geo_job_id}/download")
    assert dl_geo_resp.status_code == status.HTTP_200_OK
    geo_json = dl_geo_resp.json()
    assert geo_json["type"] == "FeatureCollection"
    assert len(geo_json["features"]) >= 1


def test_export_customer_data_requires_permission(client: TestClient, db_session: Session) -> None:
    engineer = create_user(db_session, "eng_exp@provedor.com.br", UserRole.ENGINEER.value)
    csrf_token = auth_client_login(client, engineer.email)

    # Engenheiro possui permissão exports:write, mas não é admin para exportar clientes (LGPD)
    resp = client.post(
        "/api/v1/exports",
        json={"format": "csv", "layers": ["customers"]},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "LGPD" in resp.json()["detail"]

    # Admin possui permissão total
    admin = create_user(db_session, "admin_exp_cust@provedor.com.br", UserRole.ADMIN.value)
    admin_token = auth_client_login(client, admin.email)
    admin_resp = client.post(
        "/api/v1/exports",
        json={"format": "csv", "layers": ["customers"]},
        headers={"X-CSRF-Token": admin_token},
    )
    assert admin_resp.status_code == status.HTTP_202_ACCEPTED


def test_job_cancellation(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin_cancel@provedor.com.br", UserRole.ADMIN.value)
    csrf_token = auth_client_login(client, admin.email)

    resp = client.post(
        "/api/v1/exports",
        json={"format": "csv", "layers": ["sites"]},
        headers={"X-CSRF-Token": csrf_token},
    )
    job_id = resp.json()["job_id"]

    # Cancelar o job
    cancel_resp = client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert cancel_resp.status_code == status.HTTP_200_OK
    assert cancel_resp.json()["status"] == "cancelled"


def test_worker_crash_recovery_and_lease_expiration(db_session: Session) -> None:
    job = AsyncJob(
        type="export_csv",
        status="running",
        idempotency_key="job-crash-test",
        lease_owner="crashed-worker",
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=10),
        retry_count=0,
        max_retries=3,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Novo worker deve recuperar o job e incrementar retry_count
    recovered_job = claim_next_job(db_session, worker_id="recovered-worker")
    assert recovered_job is not None
    assert recovered_job.id == job.id
    assert recovered_job.retry_count == 1
    assert recovered_job.lease_owner == "recovered-worker"
