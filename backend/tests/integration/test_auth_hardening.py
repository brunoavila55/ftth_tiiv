"""R09 (SEC-06/07/08/09/18): login, sessões, CSRF e cabeçalhos de proxy."""

from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppException
from app.core.security import generate_csrf_token, verify_csrf_tokens
from app.main import create_app
from app.modules.identity.models import LoginAttempt, User, UserSession
from app.modules.identity.service import authenticate_user, change_user_password
from tests.conftest import DEFAULT_TEST_PASSWORD, create_test_user, login_test_client

PWD = DEFAULT_TEST_PASSWORD


# ----------------------------------------------------------------------------------------------
# SEC-06 — rate limit por par (IP, e-mail), com backoff progressivo e teto por IP
# ----------------------------------------------------------------------------------------------


def _fail(db: Session, email: str, ip: str) -> None:
    with pytest.raises(AppException) as exc:
        authenticate_user(db, email, "senha-errada-xyz", ip)
    assert exc.value.status_code == 401


def test_failures_from_one_ip_do_not_block_correct_login_from_another_ip(
    db_session: Session,
) -> None:
    create_test_user(db_session, "vitima@provedor.com.br", "viewer")
    for _ in range(5):
        _fail(db_session, "vitima@provedor.com.br", "203.0.113.10")

    # o IP do atacante está bloqueado para esse e-mail...
    with pytest.raises(AppException) as blocked:
        authenticate_user(db_session, "vitima@provedor.com.br", PWD, "203.0.113.10")
    assert blocked.value.status_code == 429
    assert int(blocked.value.headers["Retry-After"]) >= 1  # type: ignore[index]

    # ...mas a vítima, de outro IP, entra normalmente
    user, token = authenticate_user(db_session, "vitima@provedor.com.br", PWD, "198.51.100.7")
    assert user.email == "vitima@provedor.com.br" and token


def test_shared_ip_does_not_lock_other_users(db_session: Session) -> None:
    create_test_user(db_session, "a@provedor.com.br", "viewer")
    create_test_user(db_session, "b@provedor.com.br", "viewer")
    for _ in range(5):
        _fail(db_session, "a@provedor.com.br", "192.0.2.50")  # CGNAT: usuário A erra
    user, _ = authenticate_user(db_session, "b@provedor.com.br", PWD, "192.0.2.50")
    assert user.email == "b@provedor.com.br"


def test_success_resets_the_pair_window(db_session: Session) -> None:
    create_test_user(db_session, "reset@provedor.com.br", "viewer")
    for _ in range(4):
        _fail(db_session, "reset@provedor.com.br", "192.0.2.60")
    authenticate_user(db_session, "reset@provedor.com.br", PWD, "192.0.2.60")  # sucesso
    for _ in range(4):  # mais 4 falhas: como a janela reiniciou, ainda não bloqueia
        _fail(db_session, "reset@provedor.com.br", "192.0.2.60")
    authenticate_user(db_session, "reset@provedor.com.br", PWD, "192.0.2.60")


def test_backoff_grows_progressively(db_session: Session) -> None:
    create_test_user(db_session, "backoff@provedor.com.br", "viewer")
    ip = "192.0.2.70"
    for _ in range(5):
        _fail(db_session, "backoff@provedor.com.br", ip)

    def wait_seconds() -> int:
        with pytest.raises(AppException) as exc:
            authenticate_user(db_session, "backoff@provedor.com.br", PWD, ip)
        assert exc.value.status_code == 429
        return int(exc.value.headers["Retry-After"])  # type: ignore[index]

    first = wait_seconds()

    def age_attempts(seconds: int) -> None:
        db_session.execute(
            update(LoginAttempt).values(
                attempted_at=LoginAttempt.attempted_at - timedelta(seconds=seconds)
            )
        )
        db_session.commit()

    age_attempts(first + 1)  # esperou o backoff: nova tentativa é permitida
    _fail(db_session, "backoff@provedor.com.br", ip)  # 6ª falha
    assert wait_seconds() > first  # a espera cresceu


def test_per_ip_ceiling_blocks_password_spraying(db_session: Session) -> None:
    ip = "192.0.2.80"
    for i in range(50):
        _fail(db_session, f"alvo{i}@provedor.com.br", ip)  # e-mails distintos (spraying)
    with pytest.raises(AppException) as exc:
        authenticate_user(db_session, "alvo-novo@provedor.com.br", "x", ip)
    assert exc.value.status_code == 429


# ----------------------------------------------------------------------------------------------
# SEC-07 — respostas indistinguíveis
# ----------------------------------------------------------------------------------------------


def _login_raw(client: TestClient, email: str, password: str):  # type: ignore[no-untyped-def]
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": token},
    )


def test_login_errors_are_indistinguishable(client: TestClient, db_session: Session) -> None:
    create_test_user(db_session, "ativo@provedor.com.br", "viewer")
    inactive = create_test_user(db_session, "inativo@provedor.com.br", "viewer")
    inactive.is_active = False
    db_session.commit()

    responses = [
        _login_raw(client, "ativo@provedor.com.br", "senha-errada-xyz"),  # senha errada
        _login_raw(client, "naoexiste@provedor.com.br", "senha-errada-xyz"),  # inexistente
        _login_raw(client, "inativo@provedor.com.br", PWD),  # desativado, senha CERTA
        _login_raw(client, "inativo@provedor.com.br", "senha-errada-xyz"),  # desativado, errada
    ]
    shapes = {
        (r.status_code, r.json()["code"], r.json()["detail"], r.json()["title"]) for r in responses
    }
    assert len(shapes) == 1, shapes
    assert responses[0].status_code == status.HTTP_401_UNAUTHORIZED


# ----------------------------------------------------------------------------------------------
# SEC-08 — troca/reset de senha revoga as outras sessões
# ----------------------------------------------------------------------------------------------


def _active_sessions(db: Session, user: User) -> int:
    db.expire_all()
    return len(
        db.scalars(
            select(UserSession).where(
                UserSession.user_id == user.id, UserSession.is_revoked.is_(False)
            )
        ).all()
    )


def test_password_change_revokes_other_sessions_but_keeps_current(
    client: TestClient, db_session: Session
) -> None:
    user = create_test_user(db_session, "troca@provedor.com.br", "viewer")
    other = TestClient(create_app(), raise_server_exceptions=False)
    login_test_client(other, user.email)  # segunda sessão (outro dispositivo)
    csrf = login_test_client(client, user.email)
    assert _active_sessions(db_session, user) == 2

    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PWD, "new_password": "NovaSenhaForte456!"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    assert _active_sessions(db_session, user) == 1
    assert client.get("/api/v1/auth/me").status_code == status.HTTP_200_OK  # a atual continua
    assert other.get("/api/v1/auth/me").status_code == status.HTTP_401_UNAUTHORIZED  # a outra caiu


def test_bootstrap_reset_password_revokes_all_sessions(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from app.cli import bootstrap_admin

    admin = create_test_user(db_session, "root@provedor.com.br", "admin")
    login_test_client(client, admin.email)
    assert _active_sessions(db_session, admin) == 1

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bootstrap_admin",
            "--email",
            admin.email,
            "--password",
            "OutraSenhaForte789!",
            "--reset-password",
        ],
    )
    assert bootstrap_admin.main() == 0
    assert _active_sessions(db_session, admin) == 0
    assert client.get("/api/v1/auth/me").status_code == status.HTTP_401_UNAUTHORIZED


def test_change_user_password_service_signature_accepts_current_session(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "svc@provedor.com.br", "viewer")
    change_user_password(db_session, user, PWD, "NovaSenhaForte456!", keep_session_id=None)


# ----------------------------------------------------------------------------------------------
# SEC-18 — X-Forwarded-For só de proxies confiáveis; valor inválido/longo é ignorado
# ----------------------------------------------------------------------------------------------


def _client_ip_seen(app_client: TestClient, xff: str) -> str:
    resp = app_client.get("/api/v1/auth/csrf", headers={"X-Forwarded-For": xff})
    assert resp.status_code == status.HTTP_200_OK
    return resp.headers["x-debug-client-ip"]


@pytest.fixture
def ip_echo_app(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """App com uma rota extra que devolve o IP resolvido, para testar o middleware de proxy."""
    from fastapi import Request

    def make(trusted: str, peer: str) -> TestClient:
        monkeypatch.setenv("TRUSTED_PROXIES", trusted)
        get_settings.cache_clear()
        app = create_app()

        @app.get("/__ip")
        def _ip(request: Request) -> dict[str, str]:
            from app.core.dependencies import get_client_ip

            return {"ip": get_client_ip(request), "scheme": request.url.scheme}

        return TestClient(app, client=(peer, 40000), raise_server_exceptions=False)

    return make


def test_xff_ignored_when_peer_is_not_a_trusted_proxy(ip_echo_app) -> None:  # type: ignore[no-untyped-def]
    client = ip_echo_app('["10.0.0.0/8"]', "203.0.113.99")  # peer público, não confiável
    body = client.get("/__ip", headers={"X-Forwarded-For": "1.2.3.4"}).json()
    assert body["ip"] == "203.0.113.99"


def test_xff_honoured_from_trusted_proxy_and_rightmost_untrusted_wins(ip_echo_app) -> None:  # type: ignore[no-untyped-def]
    client = ip_echo_app('["10.0.0.0/8"]', "10.1.2.3")
    # cliente forjou "9.9.9.9"; o proxy confiável acrescentou o IP real 198.51.100.4
    body = client.get("/__ip", headers={"X-Forwarded-For": "9.9.9.9, 198.51.100.4"}).json()
    assert body["ip"] == "198.51.100.4"
    body = client.get("/__ip", headers={"X-Forwarded-For": "198.51.100.4, 10.9.9.9"}).json()
    assert body["ip"] == "198.51.100.4"  # proxies confiáveis à direita são descartados


def test_default_trusts_no_proxy(ip_echo_app) -> None:  # type: ignore[no-untyped-def]
    client = ip_echo_app("[]", "10.1.2.3")
    assert client.get("/__ip", headers={"X-Forwarded-For": "1.2.3.4"}).json()["ip"] == "10.1.2.3"


@pytest.mark.parametrize("garbage", ["x" * 60, "não-é-ip", "1.2.3.4.5", "999.1.1.1", "", ", ,"])
def test_invalid_xff_is_ignored_and_login_does_not_500(
    ip_echo_app, db_session: Session, garbage: str
) -> None:  # type: ignore[no-untyped-def]
    client = ip_echo_app('["10.0.0.0/8"]', "10.1.2.3")
    assert client.get("/__ip", headers={"X-Forwarded-For": garbage.encode()}).json()["ip"] == "10.1.2.3"

    create_test_user(db_session, "xff@provedor.com.br", "viewer")
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "xff@provedor.com.br", "password": "errada-errada"},
        headers={"X-CSRF-Token": token, "X-Forwarded-For": garbage.encode()},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED  # nunca 500


def test_x_forwarded_proto_only_from_trusted_proxy(ip_echo_app) -> None:  # type: ignore[no-untyped-def]
    trusted = ip_echo_app('["10.0.0.0/8"]', "10.1.2.3")
    assert trusted.get("/__ip", headers={"X-Forwarded-Proto": "https"}).json()["scheme"] == "https"
    untrusted = ip_echo_app('["10.0.0.0/8"]', "203.0.113.99")
    assert untrusted.get("/__ip", headers={"X-Forwarded-Proto": "https"}).json()["scheme"] == "http"


# ----------------------------------------------------------------------------------------------
# SEC-09 — CSRF: Origin por igualdade exata e token assinado
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("origin", "expected"),
    [
        ("http://localhost:3000", status.HTTP_200_OK),  # em CORS_ORIGINS
        ("http://127.0.0.1:3000", status.HTTP_200_OK),
        ("http://localhost:3000.evil.example", status.HTTP_403_FORBIDDEN),  # startswith burlava
        ("http://localhost:30000", status.HTTP_403_FORBIDDEN),  # porta diferente
        ("https://localhost:3000", status.HTTP_403_FORBIDDEN),  # esquema diferente
        ("http://localhost", status.HTTP_403_FORBIDDEN),  # sem porta ≠ :3000
        ("http://evil.example", status.HTTP_403_FORBIDDEN),
        ("null", status.HTTP_403_FORBIDDEN),
        ("http://localhost:3000/", status.HTTP_403_FORBIDDEN),  # Origin nunca leva path
    ],
)
def test_origin_is_compared_by_exact_match(client: TestClient, origin: str, expected: int) -> None:
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token, "Origin": origin})
    assert resp.status_code in (
        expected,
        status.HTTP_204_NO_CONTENT if expected == 200 else expected,
    )
    if expected == status.HTTP_403_FORBIDDEN:
        assert resp.json()["code"] == "csrf_origin_mismatch"
    else:
        assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_csrf_token_is_signed_with_csrf_secret() -> None:
    token = generate_csrf_token()
    assert verify_csrf_tokens(token, token)
    nonce, _, signature = token.partition(".")
    assert nonce and signature
    forged = f"{nonce}.{'A' * len(signature)}"
    assert not verify_csrf_tokens(forged, forged)  # header == cookie, mas assinatura inválida
    assert not verify_csrf_tokens("qualquer-coisa-sem-assinatura", "qualquer-coisa-sem-assinatura")
    assert not verify_csrf_tokens(token, generate_csrf_token())  # tokens diferentes


def test_csrf_token_signed_with_another_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    token = generate_csrf_token()
    monkeypatch.setenv("CSRF_SECRET", "outro-segredo-csrf-com-mais-de-trinta-caracteres!!")
    get_settings.cache_clear()
    assert not verify_csrf_tokens(token, token)


def test_forged_unsigned_double_submit_is_rejected_by_the_api(client: TestClient) -> None:
    """Atacante que consegue plantar um cookie (subdomínio) não consegue forjar o par."""
    client.cookies.set("ftth_csrf_token", "token-plantado-pelo-atacante")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "x@y.com", "password": "12345678"},
        headers={"X-CSRF-Token": "token-plantado-pelo-atacante"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["code"] == "csrf_token_invalid"
