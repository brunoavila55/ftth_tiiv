from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.identity.models import User, UserSession
from app.schemas.common import UserRole


@pytest.fixture
def test_admin_user(db_session: Session) -> User:
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


def get_csrf_token_and_cookie(client: TestClient) -> tuple[str, str]:
    """Obtém token CSRF e valor do cookie para uso em testes de mutação."""
    resp = client.get("/api/v1/auth/csrf")
    assert resp.status_code == status.HTTP_200_OK
    csrf_token = resp.json()["csrf_token"]
    cookie_token = resp.cookies.get("ftth_csrf_token")
    assert cookie_token is not None
    return csrf_token, cookie_token


def test_csrf_endpoint(client: TestClient) -> None:
    csrf_token, cookie_token = get_csrf_token_and_cookie(client)
    assert csrf_token is not None
    assert len(csrf_token) >= 32
    assert csrf_token == cookie_token


def test_login_csrf_validation(client: TestClient, test_admin_user: User) -> None:
    # 1. Sem token CSRF no cabeçalho
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["code"] == "csrf_token_missing"

    # 2. Com cabeçalho mas sem cookie
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={"X-CSRF-Token": "token-aleatorio-sem-cookie"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["code"] == "csrf_cookie_missing"

    # 3. Com cookie e cabeçalho divergentes
    csrf_token, _ = get_csrf_token_and_cookie(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={"X-CSRF-Token": "token-falso-divergente"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["code"] == "csrf_token_invalid"

    # 4. Com Origin não autorizado
    csrf_token, _ = get_csrf_token_and_cookie(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={
            "X-CSRF-Token": csrf_token,
            "Origin": "https://malicious-attacker-site.com",
        },
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["code"] == "csrf_origin_mismatch"


def test_login_invalid_credentials_and_enumeration_mitigation(
    client: TestClient,
    test_admin_user: User,
) -> None:
    csrf_token, _ = get_csrf_token_and_cookie(client)

    # Senha incorreta para usuário existente
    resp_existing = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaIncorretaErrada!"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_existing.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp_existing.json()["code"] == "invalid_credentials"

    # Usuário inexistente retorna exatamente o mesmo código e formato de erro
    resp_nonexistent = client.post(
        "/api/v1/auth/login",
        json={"email": "inexistente@provedor.com.br", "password": "SenhaQualquer123!"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_nonexistent.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp_nonexistent.json()["code"] == "invalid_credentials"
    assert resp_existing.json()["detail"] == resp_nonexistent.json()["detail"]


def test_login_deactivated_user(
    client: TestClient,
    test_admin_user: User,
    db_session: Session,
) -> None:
    test_admin_user.is_active = False
    db_session.commit()

    csrf_token, _ = get_csrf_token_and_cookie(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["code"] == "user_deactivated"


def test_login_rate_limiting(
    client: TestClient,
    test_admin_user: User,
) -> None:
    csrf_token, _ = get_csrf_token_and_cookie(client)

    # 5 tentativas com falha consecutivas
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": test_admin_user.email, "password": "SenhaIncorretaErrada!"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 6ª tentativa deve ser bloqueada por rate limit (HTTP 429)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert resp.json()["code"] == "rate_limit_exceeded"


def test_login_success_and_me_lifecycle(
    client: TestClient,
    test_admin_user: User,
) -> None:
    csrf_token, _ = get_csrf_token_and_cookie(client)

    # Login com credenciais corretas
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["user"]["email"] == test_admin_user.email
    assert data["user"]["role"] == "admin"
    assert "users:read" in data["user"]["permissions"]
    assert "users:write" in data["user"]["permissions"]

    # Cookie de sessão foi setado
    assert "ftth_session" in client.cookies
    session_cookie = client.cookies.get("ftth_session")
    assert session_cookie is not None

    # Chamada a GET /auth/me usando a sessão autenticada
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == status.HTTP_200_OK
    me_data = me_resp.json()
    assert me_data["email"] == test_admin_user.email
    assert me_data["role"] == "admin"

    # Logout
    csrf_token_after_login = client.cookies.get("ftth_csrf_token")
    assert csrf_token_after_login is not None
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token_after_login},
    )
    assert logout_resp.status_code == status.HTTP_204_NO_CONTENT

    # Próxima chamada a /auth/me deve falhar pois sessão foi revogada e cookie apagado
    me_after_logout = client.get("/api/v1/auth/me")
    assert me_after_logout.status_code == status.HTTP_401_UNAUTHORIZED


def test_session_expiration_and_inactivity(
    client: TestClient,
    test_admin_user: User,
    db_session: Session,
) -> None:
    csrf_token, _ = get_csrf_token_and_cookie(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == status.HTTP_200_OK

    # Localiza sessão no banco e simula expiração por inatividade (> 24h)
    db_user_session = db_session.query(UserSession).filter_by(user_id=test_admin_user.id).first()
    assert db_user_session is not None
    db_user_session.last_activity_at = datetime.now(UTC) - timedelta(hours=25)
    db_session.commit()

    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert me_resp.json()["code"] == "invalid_session"


def test_change_password_endpoint(
    client: TestClient,
    test_admin_user: User,
) -> None:
    csrf_token, _ = get_csrf_token_and_cookie(client)
    client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={"X-CSRF-Token": csrf_token},
    )

    csrf_token_auth = client.cookies.get("ftth_csrf_token")
    assert csrf_token_auth is not None

    # Tenta alterar com senha atual errada
    resp_fail = client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "SenhaAtualIncorreta!",
            "new_password": "NovaSenhaSegura456!",
        },
        headers={"X-CSRF-Token": csrf_token_auth},
    )
    assert resp_fail.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp_fail.json()["code"] == "invalid_current_password"

    # Altera com senha correta
    resp_ok = client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "SenhaSegura123!",
            "new_password": "NovaSenhaSegura456!",
        },
        headers={"X-CSRF-Token": csrf_token_auth},
    )
    assert resp_ok.status_code == status.HTTP_204_NO_CONTENT

    # Tenta logar com a senha antiga (deve falhar)
    client.cookies.clear()
    csrf_token_new, _ = get_csrf_token_and_cookie(client)
    resp_old = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "SenhaSegura123!"},
        headers={"X-CSRF-Token": csrf_token_new},
    )
    assert resp_old.status_code == status.HTTP_401_UNAUTHORIZED

    # Loga com a nova senha (deve suceder)
    resp_new = client.post(
        "/api/v1/auth/login",
        json={"email": test_admin_user.email, "password": "NovaSenhaSegura456!"},
        headers={"X-CSRF-Token": csrf_token_new},
    )
    assert resp_new.status_code == status.HTTP_200_OK
