import ipaddress
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import get_logger, request_id_ctx
from app.core.metrics import metrics_collector

logger = get_logger("app.middleware.request_id")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware que assegura e propaga o X-Request-ID para contexto de logs, resposta e métricas (B16)."""

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
            duration_s = time.perf_counter() - start_time
            duration_ms = round(duration_s * 1000, 2)
            response.headers["X-Request-ID"] = request_id

            # Identifica formato parametrizado da rota para manter baixa cardinalidade
            route = request.scope.get("route")
            route_format = getattr(route, "path_format", None)

            metrics_collector.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_seconds=duration_s,
                route_format=route_format,
            )

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
            duration_s = time.perf_counter() - start_time
            duration_ms = round(duration_s * 1000, 2)

            route = request.scope.get("route")
            route_format = getattr(route, "path_format", None)
            metrics_collector.record_request(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_seconds=duration_s,
                route_format=route_format,
            )

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


_MAX_XFF_LENGTH = 512  # cabeçalhos maiores são ignorados por completo
_MAX_XFF_ENTRIES = 20


class TrustedProxyMiddleware:
    """Aplica X-Forwarded-For/-Proto **somente** quando o par TCP é um proxy confiável (SEC-18).

    - o IP do cliente é a entrada mais à direita do XFF que não seja ela mesma um proxy
      confiável (as entradas à esquerda podem ter sido forjadas pelo cliente);
    - qualquer entrada que não seja um IP válido (ou cabeçalho longo demais) invalida o cabeçalho
      e o IP do socket é mantido — o valor bruto nunca chega ao banco;
    - X-Forwarded-Proto só é aceito se for http/https.
    """

    def __init__(self, app: ASGIApp, trusted_proxies: list[str]) -> None:
        self.app = app
        self.networks = [ipaddress.ip_network(entry, strict=False) for entry in trusted_proxies]

    def _is_trusted(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return any(address in network for network in self.networks)

    def _resolve_client(self, xff: str) -> str | None:
        if not xff or len(xff) > _MAX_XFF_LENGTH:
            return None
        parts = [part.strip() for part in xff.split(",")]
        if len(parts) > _MAX_XFF_ENTRIES:
            return None
        for part in reversed(parts):
            try:
                address = ipaddress.ip_address(part)
            except ValueError:
                return None  # entrada inválida: descarta o cabeçalho inteiro
            if not self._is_trusted(address):
                return str(address)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and self.networks:
            client = scope.get("client")
            try:
                peer = ipaddress.ip_address(client[0]) if client else None
            except ValueError:
                peer = None
            if peer is not None and self._is_trusted(peer):
                xff_values = [v for n, v in scope["headers"] if n == b"x-forwarded-for"]
                if xff_values:
                    joined = b", ".join(xff_values).decode("latin1")
                    resolved = self._resolve_client(joined)
                    if resolved:
                        scope["client"] = (resolved, 0)
                proto_values = [v for n, v in scope["headers"] if n == b"x-forwarded-proto"]
                if proto_values:
                    proto = proto_values[-1].decode("latin1").strip()
                    if proto in ("http", "https"):
                        scope["scheme"] = proto
        await self.app(scope, receive, send)
