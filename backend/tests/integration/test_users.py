import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.identity.models import User
from app.schemas.common import UserRole


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        email="admin@provedor.com.br",
        name="Admin Provedor",
        password_hash=hash_password("SenhaSegura123!"),
        role=UserRole.ADMIN.value,
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
        email="tecnico@provedor.com.br",
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


def login_and_get_client(client: TestClient, email: str, password: str = "SenhaSegura123!") -> str:
    """Faz login e retorna o token CSRF autenticado."""
    csrf_resp = client.get("/api/v1/auth/csrf")
    csrf_token = csrf_resp.json()["csrf_token"]

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert login_resp.status_code == status.HTTP_200_OK
    auth_csrf = client.cookies.get("ftth_csrf_token")
    assert auth_csrf is not None
    return str(auth_csrf)


def test_users_rbac_restrictions(
    client: TestClient,
    admin_user: User,
    technician_user: User,
) -> None:
    # 1. Técnico tenta listar usuários -> 403 Forbidden
    login_and_get_client(client, technician_user.email)
    resp = client.get("/api/v1/users")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["code"] == "insufficient_permissions"

    # 2. Logout e login como Admin -> 200 OK
    client.cookies.clear()
    login_and_get_client(client, admin_user.email)
    resp_admin = client.get("/api/v1/users")
    assert resp_admin.status_code == status.HTTP_200_OK
    data = resp_admin.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


def test_user_creation_and_duplicate_handling(
    client: TestClient,
    admin_user: User,
) -> None:
    auth_csrf = login_and_get_client(client, admin_user.email)

    # Cria novo usuário com sucesso
    create_resp = client.post(
        "/api/v1/users",
        json={
            "name": "Engenheiro Rede",
            "email": "engenheiro@provedor.com.br",
            "password": "SenhaEngenheiro123!",
            "role": "engineer",
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    data = create_resp.json()
    assert data["email"] == "engenheiro@provedor.com.br"
    assert data["role"] == "engineer"
    assert data["version"] == 1
    assert create_resp.headers.get("ETag") == '"1"'

    # Tentativa de criar com o mesmo e-mail -> 409 Conflict
    dup_resp = client.post(
        "/api/v1/users",
        json={
            "name": "Outro Engenheiro",
            "email": "engenheiro@provedor.com.br",
            "password": "OutraSenha123!",
            "role": "engineer",
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert dup_resp.status_code == status.HTTP_409_CONFLICT
    assert dup_resp.json()["code"] == "email_already_registered"


def test_user_update_optimistic_concurrency(
    client: TestClient,
    admin_user: User,
) -> None:
    auth_csrf = login_and_get_client(client, admin_user.email)

    # Cria usuário para teste
    create_resp = client.post(
        "/api/v1/users",
        json={
            "name": "Para Atualizar",
            "email": "atualizar@provedor.com.br",
            "password": "SenhaQualquer123!",
            "role": "viewer",
        },
        headers={"X-CSRF-Token": auth_csrf},
    )
    user_id = create_resp.json()["id"]

    # 1. Sem cabeçalho If-Match -> 428 Precondition Required
    resp_no_if_match = client.patch(
        f"/api/v1/users/{user_id}",
        json={"name": "Novo Nome Sem If Match"},
        headers={"X-CSRF-Token": auth_csrf},
    )
    assert resp_no_if_match.status_code == status.HTTP_428_PRECONDITION_REQUIRED

    # 2. Com If-Match desatualizado -> 412 Precondition Failed
    resp_wrong_match = client.patch(
        f"/api/v1/users/{user_id}",
        json={"name": "Novo Nome Versao Errada"},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"999"'},
    )
    assert resp_wrong_match.status_code == status.HTTP_412_PRECONDITION_FAILED

    # 3. Com If-Match correto -> 200 OK e version incrementada
    resp_ok = client.patch(
        f"/api/v1/users/{user_id}",
        json={"name": "Nome Atualizado com Sucesso"},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": '"1"'},
    )
    assert resp_ok.status_code == status.HTTP_200_OK
    updated_data = resp_ok.json()
    assert updated_data["name"] == "Nome Atualizado com Sucesso"
    assert updated_data["version"] == 2
    assert resp_ok.headers.get("ETag") == '"2"'


def test_last_active_admin_protection(
    client: TestClient,
    admin_user: User,
) -> None:
    auth_csrf = login_and_get_client(client, admin_user.email)

    # Tenta desativar o único admin do sistema -> 409 Conflict (last_admin_protection)
    resp_deactivate = client.patch(
        f"/api/v1/users/{admin_user.id}",
        json={"is_active": False},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": f'"{admin_user.version}"'},
    )
    assert resp_deactivate.status_code == status.HTTP_409_CONFLICT
    assert resp_deactivate.json()["code"] == "last_admin_protection"

    # Tenta rebaixar o único admin para viewer -> 409 Conflict
    resp_demote = client.patch(
        f"/api/v1/users/{admin_user.id}",
        json={"role": "viewer"},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": f'"{admin_user.version}"'},
    )
    assert resp_demote.status_code == status.HTTP_409_CONFLICT
    assert resp_demote.json()["code"] == "last_admin_protection"

    # Tenta deletar o único admin -> 409 Conflict
    resp_delete = client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers={"X-CSRF-Token": auth_csrf, "If-Match": f'"{admin_user.version}"'},
    )
    assert resp_delete.status_code == status.HTTP_409_CONFLICT
    assert resp_delete.json()["code"] == "last_admin_protection"

    # Cria um segundo admin
    client.post(
        "/api/v1/users",
        json={
            "name": "Segundo Admin",
            "email": "admin2@provedor.com.br",
            "password": "SenhaAdmin2_123!",
            "role": "admin",
        },
        headers={"X-CSRF-Token": auth_csrf},
    )

    # Agora a desativação do primeiro admin é permitida
    resp_allow = client.patch(
        f"/api/v1/users/{admin_user.id}",
        json={"is_active": False},
        headers={"X-CSRF-Token": auth_csrf, "If-Match": f'"{admin_user.version}"'},
    )
    assert resp_allow.status_code == status.HTTP_200_OK
    assert resp_allow.json()["is_active"] is False
