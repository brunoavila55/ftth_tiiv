from typing import Any

from fastapi import APIRouter, Response, status

from app.core.contracts import pending_endpoint
from app.schemas.auth import (
    ChangePasswordRequest,
    CSRFResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
)

auth_router = APIRouter(prefix="/auth", tags=["Autenticação"])


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login de usuário",
    description="Autentica via e-mail e senha, define cookie HttpOnly seguro de sessão e rotaciona token.",
)
def login(payload: LoginRequest, response: Response) -> Any:
    pending_endpoint("B03")


@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout de usuário",
    description="Invalida a sessão ativa no banco de dados e limpa os cookies de sessão.",
)
def logout() -> None:
    pending_endpoint("B03")


@auth_router.get(
    "/me",
    response_model=MeResponse,
    summary="Obter usuário autenticado",
    description="Retorna identificador, nome, e-mail, perfil e permissões granulares da sessão ativa.",
)
def get_me() -> Any:
    pending_endpoint("B03")


@auth_router.get(
    "/csrf",
    response_model=CSRFResponse,
    summary="Obter token CSRF",
    description="Retorna token CSRF e define cookie de vínculo para validação de mutações.",
)
def get_csrf() -> Any:
    pending_endpoint("B03")


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Alterar senha do usuário atual",
    description="Atualiza a senha do usuário autenticado mediante confirmação da senha atual.",
)
def change_password(payload: ChangePasswordRequest) -> None:
    pending_endpoint("B03")
