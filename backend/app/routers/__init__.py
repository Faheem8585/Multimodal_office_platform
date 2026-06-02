"""Aggregate API router. Mounted under the versioned prefix in main.py.

Each feature/module contributes a router here so main.py stays declarative and
modules stay pluggable (add a router, wire it in one place).
"""

from fastapi import APIRouter

from app.modules.finance.router import router as finance_router
from app.modules.hr.router import router as hr_router
from app.modules.it.router import router as it_router
from app.routers import (
    approvals,
    auth,
    chat,
    dashboard,
    documents,
    notifications,
    reports,
    search,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(chat.router)
api_router.include_router(approvals.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)

# Pluggable department modules.
api_router.include_router(hr_router)
api_router.include_router(finance_router)
api_router.include_router(it_router)

__all__ = [
    "api_router",
    "auth",
    "documents",
    "search",
    "chat",
    "approvals",
    "notifications",
]
