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


@pytest.fixture
def viewer_user(db_session: Session) -> User:
    user = User(
        email="viewer@provedor.com.br",
        name="Visualizador Rede",
        password_hash=hash_password("SenhaSegura123!"),
        role=UserRole.VIEWER.value,
        is_active=True,
        version=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def technician_user(db_session: Session) -> User:
    user = User(
        email="tec@provedor.com.br",
        name="Tecnico Campo",
        password_hash=hash_password("SenhaSegura123!"),
        role=UserRole.TECHNICIAN.value,
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


def test_site_lifecycle_and_optimistic_concurrency(
    client: TestClient,
    engineer_user: User,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # 1. Criação do site com geometria GeoJSON WGS84
    payload = {
        "code": "POP-CENTRO",
        "name": "POP Central Operacional",
        "kind": "pop",
        "location": {"type": "Point", "coordinates": [-46.633308, -23.550520]},
        "status": "installed",
        "address": "Av. Central, 100",
        "notes": "Ponto de presença principal",
    }
    create_resp = client.post(
        "/api/v1/sites",
        json=payload,
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    site_data = create_resp.json()
    site_id = site_data["id"]
    assert site_data["code"] == "POP-CENTRO"
    assert site_data["location"]["coordinates"] == [-46.633308, -23.550520]
    assert site_data["version"] == 1
    assert create_resp.headers.get("ETag") == '"1"'

    # 2. Rejeição de código duplicado
    dup_resp = client.post(
        "/api/v1/sites",
        json=payload,
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert dup_resp.status_code == status.HTTP_409_CONFLICT
    assert dup_resp.json()["code"] == "code_already_exists"

    # 3. Consulta por ID
    get_resp = client.get(f"/api/v1/sites/{site_id}")
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.headers.get("ETag") == '"1"'

    # 4. Atualização sem If-Match (428)
    patch_no_match = client.patch(
        f"/api/v1/sites/{site_id}",
        json={"name": "POP Central Atualizado"},
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert patch_no_match.status_code == status.HTTP_428_PRECONDITION_REQUIRED

    # 5. Atualização com If-Match desatualizado (412)
    patch_stale = client.patch(
        f"/api/v1/sites/{site_id}",
        json={"name": "POP Central Atualizado"},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"99"'},
    )
    assert patch_stale.status_code == status.HTTP_412_PRECONDITION_FAILED

    # 6. Atualização concorrente válida (200)
    patch_ok = client.patch(
        f"/api/v1/sites/{site_id}",
        json={"name": "POP Central Atualizado", "address": "Av. Central, 150"},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert patch_ok.status_code == status.HTTP_200_OK
    assert patch_ok.json()["name"] == "POP Central Atualizado"
    assert patch_ok.json()["version"] == 2
    assert patch_ok.headers.get("ETag") == '"2"'

    # 7. Exclusão bem-sucedida de site sem dependências (204)
    delete_resp = client.delete(
        f"/api/v1/sites/{site_id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"2"'},
    )
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT


def test_site_coordinates_validation(
    client: TestClient,
    engineer_user: User,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # Latitude inválida (> 90)
    resp_lat = client.post(
        "/api/v1/sites",
        json={
            "code": "POP-LAT-INVALIDA",
            "name": "POP Inválido",
            "kind": "pop",
            "location": {"type": "Point", "coordinates": [-46.633308, 95.0]},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_lat.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Longitude inválida (> 180)
    resp_lon = client.post(
        "/api/v1/sites",
        json={
            "code": "POP-LON-INVALIDA",
            "name": "POP Inválido",
            "kind": "pop",
            "location": {"type": "Point", "coordinates": [185.0, -23.550520]},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_lon.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_site_referenced_deletion_protection(
    client: TestClient,
    engineer_user: User,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # Cria site
    site_resp = client.post(
        "/api/v1/sites",
        json={
            "code": "POP-PROTEGIDO",
            "name": "POP Protegido",
            "kind": "pop",
            "location": {"type": "Point", "coordinates": [-46.633308, -23.550520]},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    site_id = site_resp.json()["id"]

    # Cria estrutura vinculada ao site
    client.post(
        "/api/v1/structures",
        json={
            "code": "CEO-01-POP",
            "kind": "ceo",
            "location": {"type": "Point", "coordinates": [-46.633308, -23.550520]},
            "site_id": site_id,
            "capacity": 48,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )

    # Tenta excluir o site referenciado -> 409 Conflict
    del_resp = client.delete(
        f"/api/v1/sites/{site_id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert del_resp.status_code == status.HTTP_409_CONFLICT
    assert del_resp.json()["code"] == "referenced_entity_conflict"

    # Confirma que o site permanece intacto no banco de dados
    assert client.get(f"/api/v1/sites/{site_id}").status_code == status.HTTP_200_OK


def test_structure_can_be_unlinked_from_site(
    client: TestClient,
    engineer_user: User,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)
    site_resp = client.post(
        "/api/v1/sites",
        json={
            "code": "POP-DESVINCULAR",
            "name": "POP para desvincular",
            "kind": "pop",
            "location": {"type": "Point", "coordinates": [-51.2, -30.1]},
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    site_id = site_resp.json()["id"]
    structure_resp = client.post(
        "/api/v1/structures",
        json={
            "code": "CEO-DESVINCULAR",
            "kind": "ceo",
            "location": {"type": "Point", "coordinates": [-51.2, -30.1]},
            "site_id": site_id,
            "capacity": 24,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    structure = structure_resp.json()

    unlink_resp = client.patch(
        f"/api/v1/structures/{structure['id']}",
        json={"site_id": None},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": f'"{structure["version"]}"'},
    )

    assert unlink_resp.status_code == status.HTTP_200_OK, unlink_resp.text
    assert unlink_resp.json()["site_id"] is None


def test_site_rbac_permissions(
    client: TestClient,
    viewer_user: User,
    technician_user: User,
    engineer_user: User,
) -> None:
    # 1. Visualizador pode ler mas não pode criar/editar/excluir
    auth_viewer = auth_client_login(client, viewer_user.email)
    list_resp = client.get("/api/v1/sites")
    assert list_resp.status_code == status.HTTP_200_OK

    create_viewer = client.post(
        "/api/v1/sites",
        json={
            "code": "POP-VIEWER",
            "name": "POP Viewer",
            "kind": "pop",
            "location": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
        },
        headers={"X-CSRF-Token": auth_viewer},
    )
    assert create_viewer.status_code == status.HTTP_403_FORBIDDEN
    assert create_viewer.json()["code"] == "insufficient_permissions"

    # 2. Técnico também não possui permissão network:write para sites
    client.cookies.clear()
    auth_tech = auth_client_login(client, technician_user.email)
    create_tech = client.post(
        "/api/v1/sites",
        json={
            "code": "POP-TECH",
            "name": "POP Tech",
            "kind": "pop",
            "location": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
        },
        headers={"X-CSRF-Token": auth_tech},
    )
    assert create_tech.status_code == status.HTTP_403_FORBIDDEN
    assert create_tech.json()["code"] == "insufficient_permissions"
