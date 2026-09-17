from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import UserRole


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="E-mail corporativo do usuário")
    password: str = Field(..., min_length=1, description="Senha do usuário")


class MeResponse(BaseModel):
    id: str = Field(..., description="UUID do usuário autenticado")
    name: str = Field(..., description="Nome de exibição do usuário")
    email: str = Field(..., description="E-mail corporativo do usuário")
    role: UserRole = Field(..., description="Função e perfil de acesso do usuário")
    permissions: list[str] = Field(
        ..., description="Lista de permissões granulares concedidas ao usuário"
    )


class LoginResponse(BaseModel):
    user: MeResponse = Field(..., description="Dados do usuário logado")
    message: str = Field(default="Login realizado com sucesso", description="Mensagem de retorno")


class CSRFResponse(BaseModel):
    csrf_token: str = Field(
        ..., description="Token CSRF que deve ser enviado no cabeçalho X-CSRF-Token"
    )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Senha atual do usuário")
    new_password: str = Field(
        ..., min_length=8, description="Nova senha com no mínimo 8 caracteres"
    )


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, description="Nome completo do usuário")
    email: EmailStr = Field(..., description="E-mail único do usuário")
    role: UserRole = Field(default=UserRole.VIEWER, description="Perfil de acesso inicial")
    password: str = Field(..., min_length=8, description="Senha inicial gerada pelo administrador")


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2)
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
