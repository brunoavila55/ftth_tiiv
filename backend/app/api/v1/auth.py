from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    SESSION_COOKIE_NAME,
    clear_session_cookies,
    get_client_ip,
    get_current_user,
    set_csrf_cookie,
    set_session_cookie,
    validate_csrf,
)
from app.core.security import generate_csrf_token
from app.db.session import get_db
from app.modules.identity.models import User
from app.modules.identity.service import (
    authenticate_user,
    change_user_password,
    revoke_session_by_token,
    user_to_me_response,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    CSRFResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
)

auth_router = APIRouter(prefix="/auth", tags=["Autenticação"])


@auth_router.get(
    "/csrf",
    response_model=CSRFResponse,
    summary="Obter token CSRF",
    description="Retorna token CSRF e define cookie de vínculo para validação de mutações.",
)
def get_csrf(response: Response) -> CSRFResponse:
    token = generate_csrf_token()
    set_csrf_cookie(response, token)
    return CSRFResponse(csrf_token=token)


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login de usuário",
    description="Autentica via e-mail e senha, define cookie HttpOnly seguro de sessão e rotaciona token.",
    dependencies=[Depends(validate_csrf)],
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    user, raw_session_token = authenticate_user(
        session=db,
        email=payload.email,
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Define cookie de sessão HttpOnly seguro
    set_session_cookie(response, raw_session_token)

    # Rotaciona token CSRF após login bem-sucedido
    new_csrf_token = generate_csrf_token()
    set_csrf_cookie(response, new_csrf_token)

    return LoginResponse(
        user=user_to_me_response(user),
        message="Login realizado com sucesso",
    )


@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout de usuário",
    description="Invalida a sessão ativa no banco de dados e limpa os cookies de sessão.",
    dependencies=[Depends(validate_csrf)],
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:].strip()

    if raw_token:
        revoke_session_by_token(db, raw_token)

    clear_session_cookies(response)


@auth_router.get(
    "/me",
    response_model=MeResponse,
    summary="Obter usuário autenticado",
    description="Retorna identificador, nome, e-mail, perfil e permissões granulares da sessão ativa.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    return user_to_me_response(current_user)


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Alterar senha do usuário atual",
    description="Atualiza a senha do usuário autenticado mediante confirmação da senha atual.",
    # get_current_user primeiro: anônimo recebe 401 (não 403 de CSRF)
    dependencies=[Depends(get_current_user), Depends(validate_csrf)],
)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    change_user_password(
        session=db,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
