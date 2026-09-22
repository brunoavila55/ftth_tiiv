import pytest
from fastapi import status
from fastapi.testclient import TestClient
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


def test_structure_lifecycle_and_kinds(
    client: TestClient,
    engineer_user: User,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # 1. Cria CTO
    create_resp = client.post(
        "/api/v1/structures",
        json={
            "code": "CTO-01-CENTRO",
            "kind": "cto",
            "location": {"type": "Point", "coordinates": [-46.634120, -23.551200]},
            "capacity": 16,
            "status": "installed",
            "condition": "ok",
            "notes": "CTO de atendimento de clientes",
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    data = create_resp.json()
    struct_id = data["id"]
    assert data["code"] == "CTO-01-CENTRO"
    assert data["kind"] == "cto"
    assert data["capacity"] == 16
    assert data["version"] == 1
    assert create_resp.headers.get("ETag") == '"1"'

    # 2. Cria Poste
    client.post(
        "/api/v1/structures",
        json={
            "code": "POSTE-01",
            "kind": "pole",
            "location": {"type": "Point", "coordinates": [-46.634200, -23.551300]},
            "capacity": 0,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )

    # 3. Cria rack interno (usado pelo seed demo dentro do POP)
    rack_resp = client.post(
        "/api/v1/structures",
        json={
            "code": "RACK-POP-01",
            "kind": "rack",
            "location": {"type": "Point", "coordinates": [-46.634300, -23.551400]},
            "capacity": 48,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert rack_resp.status_code == status.HTTP_201_CREATED
    assert rack_resp.json()["kind"] == "rack"

    # 4. Listar filtrando por kind=cto
    list_ctos = client.get("/api/v1/structures?kind=cto")
    assert list_ctos.status_code == status.HTTP_200_OK
    cto_data = list_ctos.json()
    assert cto_data["total"] == 1
    assert cto_data["items"][0]["code"] == "CTO-01-CENTRO"

    # 5. Atualização com If-Match correto
    patch_resp = client.patch(
        f"/api/v1/structures/{struct_id}",
        json={"capacity": 24, "notes": "Capacidade ampliada para 24"},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.json()["capacity"] == 24
    assert patch_resp.json()["version"] == 2
    assert patch_resp.headers.get("ETag") == '"2"'

    # 6. Exclusão bem-sucedida (204)
    del_resp = client.delete(
        f"/api/v1/structures/{struct_id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"2"'},
    )
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT


def test_structure_referenced_deletion_protection(
    client: TestClient,
    engineer_user: User,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # Cria estrutura (CTO)
    struct_resp = client.post(
        "/api/v1/structures",
        json={
            "code": "CTO-COM-PORTA",
            "kind": "cto",
            "location": {"type": "Point", "coordinates": [-46.634120, -23.551200]},
            "capacity": 8,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    struct_id = struct_resp.json()["id"]

    # Cria porta diretamente na estrutura (CTO)
    client.post(
        "/api/v1/ports",
        json={
            "name": "Porta 01",
            "role": "client_access",
            "structure_id": struct_id,
            "connector_type": "SC/APC",
        },
        headers={"X-CSRF-Token": auth_csrf},
    )

    # Tenta excluir a estrutura que possui portas -> 409 Conflict
    del_resp = client.delete(
        f"/api/v1/structures/{struct_id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert del_resp.status_code == status.HTTP_409_CONFLICT
    assert del_resp.json()["code"] == "referenced_entity_conflict"
