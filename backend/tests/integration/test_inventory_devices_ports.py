import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.identity.models import User
from app.schemas.common import UserRole


@pytest.fixture
def engineer_user(db_session: Session) -> User:
    user = User(
        email="eng@provedor.com.br",
        name="Engenheiro Telecom",
        password_hash=hash_password("SenhaSegura123!"),
        role=UserRole.ENGINEER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_client_login(client: TestClient, email: str, password: str = "SenhaSegura123!") -> str:
    csrf_resp = client.get("/api/v1/auth/csrf")
    csrf_token = csrf_resp.json()["csrf_token"]
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert login_resp.status_code == status.HTTP_200_OK
    cookie_token = client.cookies.get("ftth_csrf_token")
    assert cookie_token is not None
    return str(cookie_token)


def test_device_location_check_constraint(
    client: TestClient,
    engineer_user: User,
    db_session: Session,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # Cria um site e uma estrutura para teste
    site_resp = client.post(
        "/api/v1/sites",
        json={
            "code": "POP-DEVICE-TEST",
            "name": "POP Teste Dispositivo",
            "kind": "pop",
            "location": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    site_id = site_resp.json()["id"]

    struct_resp = client.post(
        "/api/v1/structures",
        json={
            "code": "CEO-DEVICE-TEST",
            "kind": "ceo",
            "location": {"type": "Point", "coordinates": [-46.6334, -23.5506]},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    struct_id = struct_resp.json()["id"]

    # 1. API: Rejeita dispositivo sem localidade (nenhum dos dois) -> 422
    resp_none = client.post(
        "/api/v1/devices",
        json={
            "code": "OLT-SEM-LOCAL",
            "kind": "olt",
            "manufacturer": "Huawei",
            "model": "MA5800-X7",
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_none.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. API: Rejeita dispositivo com ambas as localidades (site E structure) -> 422
    resp_both = client.post(
        "/api/v1/devices",
        json={
            "code": "OLT-DUPLO-LOCAL",
            "kind": "olt",
            "manufacturer": "Huawei",
            "model": "MA5800-X7",
            "site_id": site_id,
            "structure_id": struct_id,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_both.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. SQL Direto: Check constraint chk_device_single_location bloqueia no banco
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO devices (id, code, kind, manufacturer, model, site_id, structure_id, version, created_at, updated_at) "
                "VALUES (:id, 'OLT-RAW-INV', 'olt', 'Huawei', 'MA5800', NULL, NULL, 1, now(), now())"
            ),
            {"id": uuid.uuid4()},
        )
        db_session.commit()
    db_session.rollback()

    # 4. API: Criação bem-sucedida em site
    resp_site = client.post(
        "/api/v1/devices",
        json={
            "code": "OLT-01-POP",
            "kind": "olt",
            "manufacturer": "Huawei",
            "model": "MA5800-X7",
            "site_id": site_id,
            "status": "installed",
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_site.status_code == status.HTTP_201_CREATED
    assert resp_site.json()["site_id"] == site_id
    assert resp_site.json()["structure_id"] is None
    assert resp_site.headers.get("ETag") == '"1"'


def test_port_owner_check_constraint_and_unique_names(
    client: TestClient,
    engineer_user: User,
    db_session: Session,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # Cria site e dispositivo
    site_resp = client.post(
        "/api/v1/sites",
        json={
            "code": "POP-PORT-TEST",
            "name": "POP Teste Porta",
            "kind": "pop",
            "location": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    site_id = site_resp.json()["id"]

    dev_resp = client.post(
        "/api/v1/devices",
        json={
            "code": "OLT-PORT-TEST",
            "kind": "olt",
            "manufacturer": "ZTE",
            "model": "C300",
            "site_id": site_id,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    device_id = dev_resp.json()["id"]

    struct_resp = client.post(
        "/api/v1/structures",
        json={
            "code": "CTO-PORT-TEST",
            "kind": "cto",
            "location": {"type": "Point", "coordinates": [-46.6334, -23.5506]},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    struct_id = struct_resp.json()["id"]

    # 1. API: Rejeita porta sem proprietário (nem device, nem structure) -> 422
    resp_no_owner = client.post(
        "/api/v1/ports",
        json={"name": "PON-1", "role": "pon"},
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_no_owner.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. API: Rejeita porta com ambos os proprietários -> 422
    resp_both_owners = client.post(
        "/api/v1/ports",
        json={"name": "PON-1", "role": "pon", "device_id": device_id, "structure_id": struct_id},
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_both_owners.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. SQL Direto: Check constraint chk_port_single_owner bloqueia no banco
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO ports (id, name, role, device_id, structure_id, version, created_at, updated_at) "
                "VALUES (:id, 'PON-RAW', 'pon', NULL, NULL, 1, now(), now())"
            ),
            {"id": uuid.uuid4()},
        )
        db_session.commit()
    db_session.rollback()

    # 4. Cria porta válida no dispositivo
    p1_resp = client.post(
        "/api/v1/ports",
        json={"name": "PON-1", "role": "pon", "device_id": device_id, "connector_type": "SC/APC"},
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert p1_resp.status_code == status.HTTP_201_CREATED
    p1_id = p1_resp.json()["id"]

    # 5. Rejeita nome duplicado no mesmo dispositivo -> 409 Conflict
    dup_resp = client.post(
        "/api/v1/ports",
        json={"name": "PON-1", "role": "pon", "device_id": device_id},
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert dup_resp.status_code == status.HTTP_409_CONFLICT
    assert dup_resp.json()["code"] == "port_name_already_exists"

    # 6. Permite mesmo nome em outro proprietário (ex: estrutura CTO)
    p_struct = client.post(
        "/api/v1/ports",
        json={"name": "PON-1", "role": "client_access", "structure_id": struct_id},
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert p_struct.status_code == status.HTTP_201_CREATED

    # 7. Dispositivo com portas não pode ser excluído -> 409 Conflict
    del_dev = client.delete(
        f"/api/v1/devices/{device_id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert del_dev.status_code == status.HTTP_409_CONFLICT
    assert del_dev.json()["code"] == "referenced_entity_conflict"

    # 8. Exclui a porta primeiro com If-Match
    del_port = client.delete(
        f"/api/v1/ports/{p1_id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert del_port.status_code == status.HTTP_204_NO_CONTENT

    # 9. Agora a exclusão do dispositivo é permitida
    del_dev_ok = client.delete(
        f"/api/v1/devices/{device_id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert del_dev_ok.status_code == status.HTTP_204_NO_CONTENT
