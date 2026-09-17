from typing import NoReturn

from app.core.errors import AppException


def pending_endpoint(stage: str) -> NoReturn:
    """Dispara erro 501 para endpoints cujo contrato OpenAPI já está formalizado,

    mas cuja implementação completa está planejada para etapa posterior.
    """
    raise AppException(
        status_code=501,
        code="endpoint_pending_implementation",
        title="Funcionalidade em desenvolvimento",
        detail=(
            f"Este endpoint faz parte do contrato OpenAPI v1, mas sua implementação "
            f"completa está agendada para a etapa {stage}."
        ),
    )
