from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.core.errors import PreconditionRequiredError
from app.db.session import get_db
from app.modules.identity.service import (
    create_user_by_admin,
    delete_user_by_admin,
    get_user_by_id,
    list_users_paginated,
    update_user_by_admin,
    user_to_user_read,
)
from app.schemas.auth import UserCreate, UserRead, UserUpdate
from app.schemas.common import PaginatedResponse, PaginationParams

users_router = APIRouter(prefix="/users", tags=["Usuários"])


@users_router.get(
    "",
    response_model=PaginatedResponse[UserRead],
    summary="Listar usuários",
    description="Retorna lista paginada de usuários da organização (restrito a administradores).",
    dependencies=[Depends(require_permission("users:read"))],
)
def list_users(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(default=None, description="Busca textual por nome ou e-mail"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[UserRead]:
    items, total = list_users_paginated(
        session=db,
        page=pagination.page,
        page_size=pagination.page_size,
        q=q,
    )
    return PaginatedResponse[UserRead](
        items=[user_to_user_read(u) for u in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@users_router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário",
    description="Cadastra um novo usuário no sistema.",
    dependencies=[Depends(require_permission("users:write")), Depends(validate_csrf)],
)
def create_user(
    payload: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> UserRead:
    user = create_user_by_admin(session=db, payload=payload)
    response.headers["ETag"] = f'"{user.version}"'
    return user_to_user_read(user)


@users_router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Detalhes do usuário",
    description="Retorna dados cadastrais do usuário especificado.",
    dependencies=[Depends(require_permission("users:read"))],
)
def get_user(
    user_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> UserRead:
    user = get_user_by_id(session=db, user_id=user_id)
    response.headers["ETag"] = f'"{user.version}"'
    return user_to_user_read(user)


@users_router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Atualizar usuário",
    description="Atualiza campos do usuário. Exige cabeçalho If-Match com a versão do recurso.",
    dependencies=[Depends(require_permission("users:write")), Depends(validate_csrf)],
)
def update_user(
    user_id: str,
    payload: UserUpdate,
    response: Response,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> UserRead:
    if if_match is None or not if_match.strip():
        raise PreconditionRequiredError()
    user = update_user_by_admin(session=db, user_id=user_id, payload=payload, if_match=if_match)
    response.headers["ETag"] = f'"{user.version}"'
    return user_to_user_read(user)


@users_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar usuário",
    description="Desativa o usuário da organização. Exige cabeçalho If-Match.",
    dependencies=[Depends(require_permission("users:write")), Depends(validate_csrf)],
)
def delete_user(
    user_id: str,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> None:
    if if_match is None or not if_match.strip():
        raise PreconditionRequiredError()
    delete_user_by_admin(session=db, user_id=user_id, if_match=if_match)
