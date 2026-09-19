from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.v1.health import health_router
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.metrics import metrics_collector
from app.core.metrics_store import start_metrics_heartbeat, stop_metrics_heartbeats
from app.core.middleware import RequestIDMiddleware, TrustedProxyMiddleware
from app.modules.audit.hooks import register_audit_listeners

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        f"Iniciando {settings.APP_NAME} em ambiente [{settings.ENVIRONMENT}]",
        extra={"environment": settings.ENVIRONMENT},
    )
    # Modo multiprocesso de métricas: heartbeat periódico do snapshot deste processo (idle inclusive)
    start_metrics_heartbeat(metrics_collector, role="api")
    yield
    stop_metrics_heartbeats()
    logger.info(f"Encerrando {settings.APP_NAME}")


def custom_generate_unique_id(route: APIRoute) -> str:
    """Gera operation_id determinístico e estável único por rota e path."""
    clean_path = (
        route.path_format.strip("/")
        .replace("/", "_")
        .replace("{", "")
        .replace("}", "")
        .replace("-", "_")
    )
    return f"{clean_path}_{route.name}"


def create_app() -> FastAPI:
    """Fábrica da aplicação FastAPI."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title=settings.APP_NAME,
        description="FTTH Manager — Sistema de documentação física e óptica de rede FTTH",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        generate_unique_id_function=custom_generate_unique_id,
    )

    register_audit_listeners()

    # Middlewares globais
    # X-Forwarded-* só de proxies listados em TRUSTED_PROXIES (padrão: nenhum)
    app.add_middleware(TrustedProxyMiddleware, trusted_proxies=settings.TRUSTED_PROXIES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    # Registro de tratadores de erro padronizados (RFC 7807 Problem Details)
    register_exception_handlers(app)

    # Rotas de verificação de liveness e readiness na raiz
    app.include_router(health_router, prefix="/health")

    # Rotas v1 da API
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
