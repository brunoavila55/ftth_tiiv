from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_ctx

logger = get_logger("app.core.errors")

PROBLEM_CONTENT_TYPE = "application/problem+json"


class ValidationErrorItem(BaseModel):
    field: str = Field(..., description="Nome do campo com falha de validação")
    code: str = Field(..., description="Código do erro de validação")
    message: str = Field(..., description="Mensagem descritiva do erro")


class ProblemDetails(BaseModel):
    type: str = Field(
        default="about:blank",
        description="URI que identifica o tipo do problema",
    )
    title: str = Field(..., description="Breve resumo em linguagem natural do problema")
    status: int = Field(..., description="Código de status HTTP")
    detail: str = Field(..., description="Explicação detalhada do erro para a ocorrência")
    code: str = Field(..., description="Código de erro de máquina do sistema")
    request_id: str | None = Field(
        default=None, description="Identificador único da requisição (X-Request-ID)"
    )
    errors: list[ValidationErrorItem] | None = Field(
        default=None, description="Lista de erros de validação por campo, se aplicável"
    )


class AppException(Exception):
    """Exceção base de aplicação que mapeia diretamente para Problem Details RFC 7807."""

    def __init__(
        self,
        status_code: int,
        code: str,
        title: str,
        detail: str,
        errors: list[ValidationErrorItem] | None = None,
        type_uri: str = "about:blank",
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.title = title
        self.detail = detail
        self.errors = errors
        self.type_uri = type_uri


class NotFoundError(AppException):
    def __init__(
        self,
        detail: str = "Recurso não encontrado.",
        code: str = "resource_not_found",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
            title="Recurso não encontrado",
            detail=detail,
        )


class PreconditionRequiredError(AppException):
    def __init__(
        self,
        detail: str = "O cabeçalho If-Match com a versão do recurso é obrigatório para esta operação.",
        code: str = "precondition_required",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            code=code,
            title="Precondição obrigatória",
            detail=detail,
        )


class PreconditionFailedError(AppException):
    def __init__(
        self,
        detail: str = "A versão do recurso fornecida no cabeçalho If-Match está desatualizada.",
        code: str = "precondition_failed",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            code=code,
            title="Precondição falhou",
            detail=detail,
        )


class ConflictError(AppException):
    def __init__(
        self,
        detail: str = "A operação solicitada gerou um conflito com o estado atual da rede.",
        code: str = "conflict",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            title="Conflito de negócio",
            detail=detail,
        )


class TopologyRevisionConflictError(AppException):
    def __init__(
        self,
        detail: str = "A revisão topológica esperada diverge da revisão atual da rede.",
        code: str = "topology_revision_conflict",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            title="Conflito de revisão topológica",
            detail=detail,
        )


class UnauthorizedError(AppException):
    def __init__(
        self,
        detail: str = "Autenticação necessária para acessar este recurso.",
        code: str = "unauthorized",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=code,
            title="Não autenticado",
            detail=detail,
        )


class ForbiddenError(AppException):
    def __init__(
        self,
        detail: str = "Permissões insuficientes para executar esta operação.",
        code: str = "forbidden",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            title="Acesso negado",
            detail=detail,
        )


class CSRFError(AppException):
    def __init__(
        self,
        detail: str = "Token CSRF inválido ou ausente.",
        code: str = "csrf_token_invalid",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            title="Falha na validação CSRF",
            detail=detail,
        )


class UnprocessableEntityError(AppException):
    def __init__(
        self,
        detail: str,
        code: str = "validation_error",
        field: str | None = None,
    ) -> None:
        errors = [ValidationErrorItem(field=field, code=code, message=detail)] if field else None
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=code,
            title="Erro de validação",
            detail=detail,
            errors=errors,
        )


def _build_problem_response(
    status_code: int,
    code: str,
    title: str,
    detail: str,
    errors: list[ValidationErrorItem] | None = None,
    type_uri: str = "about:blank",
) -> JSONResponse:
    req_id = request_id_ctx.get()
    problem = ProblemDetails(
        type=type_uri,
        title=title,
        status=status_code,
        detail=detail,
        code=code,
        request_id=req_id,
        errors=errors,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_CONTENT_TYPE,
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return _build_problem_response(
        status_code=exc.status_code,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        errors=exc.errors,
        type_uri=exc.type_uri,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    items: list[ValidationErrorItem] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        # Remove "body", "query", etc. do início para formar campo legível
        field_parts = [str(x) for x in loc if x not in ("body", "query", "path")]
        field_name = ".".join(field_parts) or "body"
        items.append(
            ValidationErrorItem(
                field=field_name,
                code=err.get("type", "validation_error"),
                message=err.get("msg", "Valor inválido"),
            )
        )
    return _build_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        title="Erro de validação dos dados de entrada",
        detail="Um ou mais campos fornecidos na requisição são inválidos.",
        errors=items,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = f"http_{exc.status_code}"
    title = HTTP_STATUS_TITLES.get(exc.status_code, "Erro HTTP")
    detail = str(exc.detail) if exc.detail else title
    return _build_problem_response(
        status_code=exc.status_code,
        code=code,
        title=title,
        detail=detail,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Exceção não tratada capturada", exc_info=exc)
    return _build_problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_server_error",
        title="Erro interno do servidor",
        detail="Ocorreu um erro interno inesperado. Contate o administrador com o request_id.",
    )


HTTP_STATUS_TITLES: dict[int, str] = {
    400: "Requisição inválida",
    401: "Não autenticado",
    403: "Acesso negado",
    404: "Recurso não encontrado",
    405: "Método não permitido",
    409: "Conflito de negócio",
    412: "Precondição falhou",
    422: "Entidade improcessável",
    428: "Precondição obrigatória",
    429: "Muitas requisições",
    500: "Erro interno do servidor",
    502: "Bad Gateway",
    503: "Serviço indisponível",
}


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
