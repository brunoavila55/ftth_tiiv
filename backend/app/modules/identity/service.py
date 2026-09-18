import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from app.core.errors import (
    AppException,
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    UnauthorizedError,
)
from app.core.permissions import get_role_permissions
from app.core.security import (
    dummy_verify_password,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.modules.audit.service import record_audit_event, record_contextual_event
from app.modules.identity.models import LoginAttempt, User, UserSession
from app.schemas.auth import MeResponse, UserCreate, UserRead, UserUpdate
from app.schemas.common import UserRole

# Configurações de expiração de sessão
SESSION_ABSOLUTE_EXPIRY_DAYS = 7
SESSION_INACTIVITY_EXPIRY_HOURS = 24

# Rate limit de login (SEC-06): por par (IP, e-mail), com backoff progressivo, mais um teto por IP
LOGIN_WINDOW_MINUTES = 15
LOGIN_PAIR_MAX_FAILURES = 5  # falhas do par (IP, e-mail) antes de começar o backoff
LOGIN_BACKOFF_BASE_SECONDS = 30  # espera após a 5ª falha; dobra a cada nova falha
LOGIN_BACKOFF_MAX_SECONDS = LOGIN_WINDOW_MINUTES * 60
LOGIN_IP_MAX_FAILURES = 50  # teto por IP (todas as contas): freia password spraying

INVALID_CREDENTIALS = "E-mail ou senha incorretos."
# entity_id dos eventos auth:login_failed de contas inexistentes (nunca vaza o e-mail digitado)
_UNKNOWN_LOGIN_ENTITY_ID = uuid.UUID(int=0)


def record_login_attempt(session: Session, ip_address: str, email: str, success: bool) -> None:
    attempt = LoginAttempt(
        ip_address=ip_address[:45],
        email=email.strip().lower()[:255],
        attempted_at=datetime.now(UTC),
        success=success,
    )
    session.add(attempt)
    session.commit()


def _rate_limited(retry_after: int, detail: str) -> AppException:
    return AppException(
        status_code=429,
        code="rate_limit_exceeded",
        title="Muitas tentativas de login",
        detail=detail,
        headers={"Retry-After": str(max(1, retry_after))},
    )


def check_login_rate_limit(session: Session, ip_address: str, email: str) -> None:
    """Limita tentativas por par (IP, e-mail) com backoff progressivo e por IP (teto maior).

    Falhas de um IP não bloqueiam o mesmo e-mail vindo de outro IP (ninguém trava a conta alheia)
    e falhas de um e-mail não bloqueiam outras contas do mesmo IP (CGNAT). Um login bem-sucedido
    do par reinicia a contagem daquele par.
    """
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    clean_email = email.strip().lower()[:255]
    ip_address = ip_address[:45]

    pair_filter = (LoginAttempt.ip_address == ip_address) & (LoginAttempt.email == clean_email)

    last_success = session.scalar(
        select(func.max(LoginAttempt.attempted_at)).where(
            pair_filter, LoginAttempt.success.is_(True), LoginAttempt.attempted_at >= window_start
        )
    )
    since = max(window_start, last_success) if last_success else window_start

    pair_failures, last_failure = session.execute(
        select(func.count(LoginAttempt.id), func.max(LoginAttempt.attempted_at)).where(
            pair_filter, LoginAttempt.success.is_(False), LoginAttempt.attempted_at > since
        )
    ).one()

    if pair_failures >= LOGIN_PAIR_MAX_FAILURES and last_failure is not None:
        exponent = min(pair_failures - LOGIN_PAIR_MAX_FAILURES, 10)
        wait = min(LOGIN_BACKOFF_BASE_SECONDS * 2**exponent, LOGIN_BACKOFF_MAX_SECONDS)
        remaining = wait - (now - last_failure).total_seconds()
        if remaining > 0:
            raise _rate_limited(
                int(remaining) + 1,
                f"Muitas tentativas de login sem sucesso. Aguarde {int(remaining) + 1} segundo(s).",
            )

    ip_failures, oldest_ip_failure = session.execute(
        select(func.count(LoginAttempt.id), func.min(LoginAttempt.attempted_at)).where(
            LoginAttempt.ip_address == ip_address,
            LoginAttempt.success.is_(False),
            LoginAttempt.attempted_at >= window_start,
        )
    ).one()
    if ip_failures >= LOGIN_IP_MAX_FAILURES and oldest_ip_failure is not None:
        remaining = LOGIN_WINDOW_MINUTES * 60 - (now - oldest_ip_failure).total_seconds()
        raise _rate_limited(
            int(remaining) + 1,
            "Muitas tentativas de login sem sucesso a partir deste endereço. Tente novamente mais tarde.",
        )


def authenticate_user(
    session: Session,
    email: str,
    password: str,
    ip_address: str,
    user_agent: str | None = None,
) -> tuple[User, str]:
    """Autentica o usuário com mitigação de enumeração, rate limiting e criação de sessão.

    Inexistente, desativado e senha errada produzem a MESMA resposta (status, código e corpo), e a
    senha é sempre verificada antes de qualquer decisão (tempo equivalente).
    """
    clean_email = email.strip().lower()
    check_login_rate_limit(session, ip_address, clean_email)

    user = session.scalar(select(User).where(User.email == clean_email))

    if user is None:
        dummy_verify_password(password)
        password_ok = False
    else:
        password_ok = verify_password(user.password_hash, password)

    if user is None or not password_ok or not user.is_active:
        # Auditoria sem a senha e sem o e-mail digitado (pode ser lixo/segredo); id só se a conta existe
        record_audit_event(
            session,
            actor_id=None,
            actor_name="anonymous",
            action="auth:login_failed",
            entity_type="user",
            entity_id=user.id if user is not None else _UNKNOWN_LOGIN_ENTITY_ID,
            changes={"ip_address": ip_address[:45]},
        )
        record_login_attempt(session, ip_address, clean_email, success=False)
        raise UnauthorizedError(INVALID_CREDENTIALS, code="invalid_credentials")

    # Autenticado com sucesso
    record_audit_event(
        session,
        actor_id=user.id,
        actor_name=user.name,
        action="auth:login_succeeded",
        entity_type="user",
        entity_id=user.id,
        changes={"ip_address": ip_address[:45]},
    )
    record_login_attempt(session, ip_address, clean_email, success=True)

    # Rotação de sessão: gera token novo e persiste hash
    raw_token, token_hash = generate_session_token()
    now = datetime.now(UTC)
    user_session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        ip_address=ip_address[:45],
        user_agent=user_agent[:255] if user_agent else None,
        created_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(days=SESSION_ABSOLUTE_EXPIRY_DAYS),
        is_revoked=False,
    )
    session.add(user_session)
    session.commit()

    return user, raw_token


def get_active_session_by_token(session: Session, raw_token: str) -> UserSession | None:
    """Busca sessão ativa pelo token opaco com validação de expiração e inatividade."""
    token_hash = hash_session_token(raw_token)
    user_session = session.scalar(
        select(UserSession)
        .join(User)
        .where(
            UserSession.token_hash == token_hash,
            UserSession.is_revoked.is_(False),
            User.is_active.is_(True),
        )
    )

    if not user_session:
        return None

    now = datetime.now(UTC)

    # Expiração absoluta
    if now > user_session.expires_at:
        user_session.is_revoked = True
        session.commit()
        return None

    # Expiração por inatividade
    inactivity_limit = user_session.last_activity_at + timedelta(
        hours=SESSION_INACTIVITY_EXPIRY_HOURS
    )
    if now > inactivity_limit:
        user_session.is_revoked = True
        session.commit()
        return None

    # Atualiza última atividade se passou mais de 60 segundos
    if (now - user_session.last_activity_at).total_seconds() > 60:
        user_session.last_activity_at = now
        session.commit()

    return user_session


def revoke_session_by_token(session: Session, raw_token: str) -> None:
    token_hash = hash_session_token(raw_token)
    user_session = session.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if user_session and not user_session.is_revoked:
        user_session.is_revoked = True
        user = user_session.user
        record_audit_event(
            session,
            actor_id=user.id,
            actor_name=user.name,
            action="auth:logout",
            entity_type="user",
            entity_id=user.id,
        )
        session.commit()


def revoke_user_sessions(
    session: Session, user_id: uuid.UUID, keep_session_id: uuid.UUID | None = None
) -> int:
    """Revoga todas as sessões ativas do usuário (exceto `keep_session_id`). Não faz commit."""
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    if keep_session_id is not None:
        stmt = stmt.where(UserSession.id != keep_session_id)
    result = cast(CursorResult[Any], session.execute(stmt))
    return result.rowcount or 0


def change_user_password(
    session: Session,
    user: User,
    current_password: str,
    new_password: str,
    keep_session_id: uuid.UUID | None = None,
) -> None:
    """Troca a senha e revoga as demais sessões do usuário (mantém `keep_session_id`)."""
    if not verify_password(user.password_hash, current_password):
        raise UnauthorizedError("Senha atual incorreta.", code="invalid_current_password")

    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.now(UTC)
    revoked = revoke_user_sessions(session, user.id, keep_session_id=keep_session_id)
    record_audit_event(
        session,
        actor_id=user.id,
        actor_name=user.name,
        action="auth:password_changed",
        entity_type="user",
        entity_id=user.id,
        changes={"other_sessions_revoked": revoked},
    )
    session.commit()


# --- GERENCIAMENTO DE USUÁRIOS (ADMIN) ---


def create_user_by_admin(session: Session, payload: UserCreate) -> User:
    clean_email = payload.email.strip().lower()
    existing = session.scalar(select(User).where(User.email == clean_email))
    if existing:
        raise ConflictError(
            "Já existe um usuário cadastrado com este e-mail.", code="email_already_registered"
        )

    user = User(
        email=clean_email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role.value,
        is_active=True,
        version=1,
    )
    session.add(user)
    session.flush()
    record_contextual_event(
        session,
        action="user:created",
        entity_type="user",
        entity_id=user.id,
        changes={"email": user.email, "name": user.name, "role": user.role},
    )
    session.commit()
    session.refresh(user)
    return user


def update_user_by_admin(
    session: Session, user_id: str, payload: UserUpdate, if_match: str
) -> User:
    if not if_match:
        raise PreconditionRequiredError()

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("Usuário não encontrado.", code="user_not_found") from None

    user = session.scalar(select(User).where(User.id == user_uuid))
    if not user:
        raise NotFoundError("Usuário não encontrado.", code="user_not_found")

    try:
        expected_version = int(if_match.strip('"'))
    except ValueError:
        raise PreconditionFailedError() from None

    if user.version != expected_version:
        raise PreconditionFailedError()

    # Proteção do último administrador ativo
    if user.role == UserRole.ADMIN.value:
        will_deactivate = payload.is_active is False
        will_change_role = payload.role is not None and payload.role != UserRole.ADMIN

        if will_deactivate or will_change_role:
            other_active_admins = (
                session.scalar(
                    select(func.count(User.id)).where(
                        User.role == UserRole.ADMIN.value,
                        User.is_active.is_(True),
                        User.id != user.id,
                    )
                )
                or 0
            )
            if other_active_admins == 0:
                raise ConflictError(
                    "Operação negada: não é permitido desativar ou rebaixar o único administrador ativo do sistema.",
                    code="last_admin_protection",
                )

    before = {
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }

    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.email is not None:
        clean_email = payload.email.strip().lower()
        if clean_email != user.email:
            existing = session.scalar(select(User).where(User.email == clean_email))
            if existing:
                raise ConflictError("Este e-mail já pertence a outro usuário cadastrado.")
            user.email = clean_email
    if payload.role is not None:
        user.role = payload.role.value
    if payload.is_active is not None:
        user.is_active = payload.is_active
        # Se desativado, revoga todas as sessões ativas
        if not user.is_active:
            for s in user.sessions:
                s.is_revoked = True

    user.version += 1
    user.updated_at = datetime.now(UTC)

    after = {"name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active}
    diff = {k: {"old": before[k], "new": after[k]} for k in after if before[k] != after[k]}
    if before["is_active"] and not after["is_active"]:
        action = "user:deactivated"
    elif before["role"] != after["role"]:
        action = "user:role_changed"
    else:
        action = "user:updated"
    record_contextual_event(
        session, action=action, entity_type="user", entity_id=user.id, changes=diff
    )
    session.commit()
    session.refresh(user)
    return user


def delete_user_by_admin(session: Session, user_id: str, if_match: str) -> None:
    """Desativa o usuário preservando histórico (exclusão física apenas para contas sem referências)."""
    update_user_by_admin(session, user_id, UserUpdate(is_active=False), if_match)


def get_user_by_id(session: Session, user_id: str) -> User:
    """Busca usuário pelo identificador UUID."""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise NotFoundError("Usuário não encontrado.", code="user_not_found") from None

    user = session.scalar(select(User).where(User.id == user_uuid))
    if not user:
        raise NotFoundError("Usuário não encontrado.", code="user_not_found")
    return user


def list_users_paginated(
    session: Session,
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
) -> tuple[list[User], int]:
    """Retorna lista paginada de usuários da organização com filtro de busca opcional."""
    query = select(User)
    count_query = select(func.count(User.id))

    if q and q.strip():
        term = f"%{q.strip()}%"
        filter_clause = (User.name.ilike(term)) | (User.email.ilike(term))
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    total = session.scalar(count_query) or 0
    offset = (page - 1) * page_size
    items = list(
        session.scalars(
            query.order_by(User.created_at.desc(), User.id).offset(offset).limit(page_size)
        ).all()
    )
    return items, total


def user_to_user_read(user: User) -> UserRead:
    """Converte entidade ORM User para schema de resposta UserRead."""
    return UserRead(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=UserRole(user.role),
        is_active=user.is_active,
        version=user.version,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def user_to_me_response(user: User) -> MeResponse:
    """Converte entidade ORM User para schema MeResponse com permissões resolvidas."""
    role_enum = UserRole(user.role)
    return MeResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=role_enum,
        permissions=get_role_permissions(role_enum),
    )
