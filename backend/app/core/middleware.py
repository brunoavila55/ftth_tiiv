import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, request_id_ctx

logger = get_logger("app.middleware.request_id")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware que assegura e propaga o X-Request-ID para contexto de logs e resposta."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_request_id = request.headers.get("X-Request-ID")
        if incoming_request_id and len(incoming_request_id) <= 64:
            request_id = incoming_request_id
        else:
            request_id = str(uuid.uuid4())

        # Armazena no contexto assíncrono para os logs
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id

            logger.info(
                "HTTP request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "HTTP request failed with unhandled exception",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise
        finally:
            request_id_ctx.reset(token)
