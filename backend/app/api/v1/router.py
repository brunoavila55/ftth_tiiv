from fastapi import APIRouter

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
from app.api.v1.optical import optical_router
from app.api.v1.reports import reports_router
from app.api.v1.settings import settings_router
from app.api.v1.splitters import splitters_router
from app.api.v1.topology import topology_router
from app.api.v1.users import users_router

api_v1_router = APIRouter()

# Registro de todos os routers da API v1
api_v1_router.include_router(health_router, prefix="/health")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(inventory_router)
api_v1_router.include_router(cables_router)
api_v1_router.include_router(splitters_router)
api_v1_router.include_router(connectivity_router)
api_v1_router.include_router(customers_router)
api_v1_router.include_router(topology_router)
api_v1_router.include_router(optical_router)
api_v1_router.include_router(measurements_router)
api_v1_router.include_router(map_router)
api_v1_router.include_router(attachments_router)
api_v1_router.include_router(imports_exports_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(settings_router)
