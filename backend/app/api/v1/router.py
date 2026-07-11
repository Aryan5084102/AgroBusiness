"""Aggregate API v1 router. Feature modules register their routers here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.modules.auth.api import router as auth_router
from app.modules.suppliers.api import router as suppliers_router
from app.modules.users.api import router as users_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(users_router, prefix="/users")
api_router.include_router(suppliers_router, prefix="/suppliers")

# Future modules (Phase 3+) will be included here as they are built.
