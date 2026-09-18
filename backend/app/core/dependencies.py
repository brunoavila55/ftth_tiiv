from collections.abc import Callable
from urllib.parse import urlparse

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.permissions import has_permission
from app.core.security import verify_csrf_tokens
from app.db.session import get_db
from app.modules.identity.models import User, UserSession
from app.modules.identity.service import get_active_session_by_token
from app.schemas.common import UserRole

SESSION_COOKIE_NAME = "ftth_session"
CSRF_COOKIE_NAME = "ftth_csrf_token"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 dias


def get_client_ip(request: Request) -> str:
    """Extrai endereço IP do cliente considerando proxies reversos comuns."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def set_session_cookie(response: Response, raw_token: str) -> None:
    """Define o cookie de sessão HttpOnly com flags de segurança estritas."""
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.COOKIE_SECURE or settings.is_production,
        samesite="lax",
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    """Define o cookie CSRF de vínculo lido pelo cliente web para enviar no cabeçalho."""
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE or settings.is_production,
        samesite="lax",
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    """Remove cookies de sessão e CSRF na desconexão."""
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


def validate_csrf(request: Request) -> None:
    """Valida proteção CSRF e Origin para métodos de mutação de estado."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # 1. Validação de Origin se fornecido pelo navegador
        origin = request.headers.get("origin")
        if origin:
            settings = get_settings()
            parsed_origin = urlparse(origin)
            origin_netloc = parsed_origin.netloc or origin

            allowed_origins = {urlparse(o).netloc or o for o in settings.CORS_ORIGINS}
            # Adiciona a própria origem da requisição e domínios locais de teste
            request_netloc = urlparse(str(request.base_url)).netloc
            allowed_origins.add(request_netloc)
            allowed_origins.add("localhost")
            allowed_origins.add("127.0.0.1")
            allowed_origins.add("testserver")

            is_allowed = (
                origin_netloc in allowed_origins
                or any(origin.startswith(allowed) for allowed in settings.CORS_ORIGINS)
                or origin.rstrip("/") == str(request.base_url).rstrip("/")
            )
            if not is_allowed:
                raise ForbiddenError(
                    "Origem da requisição não permitida pelo CORS/CSRF.",
                    code="csrf_origin_mismatch",
                )

        # 2. Validação do par de tokens CSRF (cabeçalho vs cookie)
        header_token = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

        if not header_token:
            raise ForbiddenError(
                "Cabeçalho X-CSRF-Token ausente para operação de escrita.",
                code="csrf_token_missing",
            )
        if not cookie_token:
            raise ForbiddenError(
                "Cookie de CSRF ausente. Obtenha um token via GET /auth/csrf.",
                code="csrf_cookie_missing",
            )
        if not verify_csrf_tokens(header_token, cookie_token):
            raise ForbiddenError(
                "Token CSRF divergente ou inválido.",
                code="csrf_token_invalid",
            )


def get_current_session(
    request: Request,
    db: Session = Depends(get_db),
) -> UserSession:
    """Recupera e valida a sessão ativa do usuário através do cookie ou Authorization Bearer."""
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        # Suporte a cabeçalho Authorization Bearer para testes automatizados ou scripts CLI
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:].strip()

    if not raw_token:
        raise UnauthorizedError(
            "Autenticação necessária. Sessão não fornecida.",
            code="authentication_required",
        )

    user_session = get_active_session_by_token(db, raw_token)
    if not user_session:
        raise UnauthorizedError(
            "Sessão inválida, revogada ou expirada. Faça login novamente.",
            code="invalid_session",
        )

    return user_session


def get_current_user(
    user_session: UserSession = Depends(get_current_session),
) -> User:
    """Extrai o usuário autenticado da sessão ativa e valida seu status."""
    user = user_session.user
    if not user or not user.is_active:
        raise ForbiddenError(
            "Esta conta de usuário foi desativada.",
            code="user_deactivated",
        )
    return user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Extrai o usuário autenticado se presente e válido; retorna None caso anônimo."""
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:].strip()

    if not raw_token:
        return None

    try:
        user_session = get_active_session_by_token(db, raw_token)
        if not user_session or not user_session.user or not user_session.user.is_active:
            return None
        return user_session.user
    except Exception:
        return None


def require_permission(permission: str) -> Callable[..., User]:
    """Fábrica de dependências para validação granular de permissões RBAC."""

    def _permission_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role = UserRole(current_user.role)
        if not has_permission(user_role, permission):
            raise ForbiddenError(
                f"Acesso negado. Requer a permissão '{permission}'.",
                code="insufficient_permissions",
            )
        return current_user

    return _permission_dependency
