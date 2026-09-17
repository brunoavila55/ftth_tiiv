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


def test_optical_profile_lifecycle_and_concurrency(
    client: TestClient,
    engineer_user: User,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # 1. Criação do perfil GPON Classe B+
    payload = {
        "name": "GPON Classe B+",
        "technology": "GPON",
        "wavelength_nm": 1490,
        "tx_min_dbm": 1.5,
        "tx_max_dbm": 5.0,
        "rx_sensitivity_dbm": -28.0,
        "rx_overload_dbm": -8.0,
        "default_attenuation_db_per_km": 0.35,
        "notes": "Perfil padrão para portas PON OLT GPON B+",
    }
    create_resp = client.post(
        "/api/v1/optical-profiles",
        json=payload,
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    data = create_resp.json()
    profile_id = data["id"]
    assert data["name"] == "GPON Classe B+"
    assert data["wavelength_nm"] == 1490
    assert data["version"] == 1
    assert create_resp.headers.get("ETag") == '"1"'

    # 2. Rejeição de nome duplicado -> 409
    dup_resp = client.post(
        "/api/v1/optical-profiles",
        json=payload,
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert dup_resp.status_code == status.HTTP_409_CONFLICT
    assert dup_resp.json()["code"] == "name_already_exists"

    # 3. Consulta por ID
    get_resp = client.get(f"/api/v1/optical-profiles/{profile_id}")
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["tx_min_dbm"] == 1.5

    # 4. Atualização sem If-Match (428)
    patch_no_match = client.patch(
        f"/api/v1/optical-profiles/{profile_id}",
        json={"notes": "Perfil revisado"},
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert patch_no_match.status_code == status.HTTP_428_PRECONDITION_REQUIRED

    # 5. Atualização válida com If-Match correto (200)
    patch_ok = client.patch(
        f"/api/v1/optical-profiles/{profile_id}",
        json={"tx_min_dbm": 2.0, "notes": "Perfil ajustado para 2 dBm mínimo"},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert patch_ok.status_code == status.HTTP_200_OK
    assert patch_ok.json()["tx_min_dbm"] == 2.0
    assert patch_ok.json()["version"] == 2
    assert patch_ok.headers.get("ETag") == '"2"'

    # 6. Exclusão bem-sucedida (204)
    del_resp = client.delete(
        f"/api/v1/optical-profiles/{profile_id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"2"'},
    )
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT


def test_optical_profile_limits_and_check_constraints(
    client: TestClient,
    engineer_user: User,
    db_session: Session,
) -> None:
    auth_csrf = auth_client_login(client, engineer_user.email)

    # 1. API: tx_min maior que tx_max -> 422
    resp_tx_inv = client.post(
        "/api/v1/optical-profiles",
        json={
            "name": "TX Inválido",
            "wavelength_nm": 1490,
            "tx_min_dbm": 6.0,
            "tx_max_dbm": 5.0,
            "rx_sensitivity_dbm": -28.0,
            "rx_overload_dbm": -8.0,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_tx_inv.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. API: rx_sensitivity maior que rx_overload -> 422
    resp_rx_inv = client.post(
        "/api/v1/optical-profiles",
        json={
            "name": "RX Inválido",
            "wavelength_nm": 1490,
            "tx_min_dbm": 1.0,
            "tx_max_dbm": 5.0,
            "rx_sensitivity_dbm": -5.0,  # Maior que -8.0
            "rx_overload_dbm": -8.0,
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_rx_inv.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. SQL Direto: Check constraint chk_optical_profile_tx bloqueia no banco
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO optical_profiles (id, name, technology, wavelength_nm, tx_min_dbm, tx_max_dbm, rx_sensitivity_dbm, rx_overload_dbm, default_attenuation_db_per_km, version, created_at, updated_at) "
                "VALUES (:id, 'RAW-TX-INV', 'GPON', 1490, 10.0, 5.0, -28.0, -8.0, 0.35, 1, now(), now())"
            ),
            {"id": uuid.uuid4()},
        )
        db_session.commit()
    db_session.rollback()


def test_optical_profile_rbac_permissions(
    client: TestClient,
    viewer_user: User,
    engineer_user: User,
) -> None:
    # Visualizador pode listar mas não pode criar
    auth_viewer = auth_client_login(client, viewer_user.email)
    list_resp = client.get("/api/v1/optical-profiles")
    assert list_resp.status_code == status.HTTP_200_OK

    create_resp = client.post(
        "/api/v1/optical-profiles",
        json={
            "name": "Perfil Viewer Proibido",
            "wavelength_nm": 1490,
            "tx_min_dbm": 1.0,
            "tx_max_dbm": 5.0,
            "rx_sensitivity_dbm": -28.0,
            "rx_overload_dbm": -8.0,
        },
        headers={"X-CSRF-Token": auth_viewer},
    )
    assert create_resp.status_code == status.HTTP_403_FORBIDDEN
    assert create_resp.json()["code"] == "insufficient_permissions"
