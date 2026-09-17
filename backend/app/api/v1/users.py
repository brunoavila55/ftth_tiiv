from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.contracts import pending_endpoint
from app.schemas.auth import UserCreate, UserRead, UserUpdate
from app.schemas.common import PaginatedResponse, PaginationParams

users_router = APIRouter(prefix="/users", tags=["Usuários"])


@users_router.get(
    "",
    response_model=PaginatedResponse[UserRead],
    summary="Listar usuários",
    description="Retorna lista paginada de usuários da organização (restrito a administradores).",
)
def list_users(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(default=None, description="Busca textual por nome ou e-mail"),
) -> Any:
    pending_endpoint("B03")


@users_router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário",
    description="Cadastra um novo usuário no sistema.",
)
def create_user(payload: UserCreate) -> Any:
    pending_endpoint("B03")


@users_router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Detalhes do usuário",
    description="Retorna dados cadastrais do usuário especificado.",
)
def get_user(user_id: str) -> Any:
    pending_endpoint("B03")


@users_router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Atualizar usuário",
    description="Atualiza campos do usuário. Exige cabeçalho If-Match com a versão do recurso.",
)
def update_user(
    user_id: str,
    payload: UserUpdate,
    if_match: str = Header(..., description="Versão atual do recurso para concorrência otimista"),
) -> Any:
    pending_endpoint("B03")


@users_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar usuário",
    description="Desativa o usuário da organização. Exige cabeçalho If-Match.",
)
def delete_user(
    user_id: str,
    if_match: str = Header(..., description="Versão atual do recurso para concorrência otimista"),
) -> None:
    pending_endpoint("B03")
