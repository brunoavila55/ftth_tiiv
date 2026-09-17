from fastapi import APIRouter

from app.api.v1.health import health_router

api_v1_router = APIRouter()

# Rotas de verificação de saúde sob /api/v1/health
api_v1_router.include_router(health_router, prefix="/health")
