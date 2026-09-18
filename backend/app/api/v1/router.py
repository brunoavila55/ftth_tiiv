from fastapi import APIRouter, Depends

from app.api.v1.attachments import attachments_router
from app.api.v1.auth import auth_router
from app.api.v1.cables import cables_router
from app.api.v1.connectivity import connectivity_router
from app.api.v1.customers import customers_router
from app.api.v1.health import health_router
from app.api.v1.imports_exports import imports_exports_router
from app.api.v1.inventory import inventory_router
from app.api.v1.map import map_router
from app.api.v1.measurements import measurements_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.optical import optical_router
from app.api.v1.reports import reports_router
from app.api.v1.settings import settings_router
from app.api.v1.splitters import splitters_router
from app.api.v1.topology import topology_router
from app.api.v1.users import users_router
from app.core.dependencies import get_current_user

api_v1_router = APIRouter()

# Autenticação por padrão (allow-by-default é proibido): todo router de negócio nasce protegido
# por `get_current_user`; a permissão específica de cada rota continua em `require_permission`.
# Ficam de fora, deliberadamente: health (sondas do orquestrador), auth (login/CSRF/logout
# precisam ser anônimos; /me e /change-password exigem sessão por rota) e metrics (aceita
# X-Metrics-Token de agentes de monitoramento ou sessão admin — ver verify_metrics_access).
# tests/integration/test_auth_by_default.py varre todas as rotas e falha se uma nascer aberta.
authenticated = [Depends(get_current_user)]

api_v1_router.include_router(health_router, prefix="/health")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router, dependencies=authenticated)
api_v1_router.include_router(inventory_router, dependencies=authenticated)
api_v1_router.include_router(cables_router, dependencies=authenticated)
api_v1_router.include_router(splitters_router, dependencies=authenticated)
api_v1_router.include_router(connectivity_router, dependencies=authenticated)
api_v1_router.include_router(customers_router, dependencies=authenticated)
api_v1_router.include_router(topology_router, dependencies=authenticated)
api_v1_router.include_router(optical_router, dependencies=authenticated)
api_v1_router.include_router(measurements_router, dependencies=authenticated)
api_v1_router.include_router(map_router, dependencies=authenticated)
api_v1_router.include_router(attachments_router, dependencies=authenticated)
api_v1_router.include_router(imports_exports_router, dependencies=authenticated)
api_v1_router.include_router(reports_router, dependencies=authenticated)
api_v1_router.include_router(settings_router, dependencies=authenticated)
api_v1_router.include_router(metrics_router)
