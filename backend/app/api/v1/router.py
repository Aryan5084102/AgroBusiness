"""Aggregate API v1 router. Feature modules register their routers here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.modules.auth.api import router as auth_router
from app.modules.catalogue.api import router as products_router
from app.modules.collections.api import router as collections_router
from app.modules.notifications.api import router as notifications_router
from app.modules.reports.api import router as reports_router
from app.modules.sales.api import router as pos_router
from app.modules.sales.wholesale_api import router as wholesale_router
from app.modules.suppliers.api import router as suppliers_router
from app.modules.users.api import router as users_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(users_router, prefix="/users")
api_router.include_router(suppliers_router, prefix="/suppliers")
api_router.include_router(products_router, prefix="/products")
api_router.include_router(pos_router, prefix="/pos")
api_router.include_router(wholesale_router, prefix="/wholesale")
api_router.include_router(collections_router, prefix="/collections")
api_router.include_router(reports_router, prefix="/reports")
api_router.include_router(notifications_router, prefix="/notifications")
