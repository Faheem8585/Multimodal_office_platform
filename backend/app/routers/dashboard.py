"""Unified role-aware dashboard endpoint."""

from fastapi import APIRouter

from app.core.deps import CurrentPrincipal, DbSession
from app.repositories.notification import ActivityRepository
from app.schemas.dashboard import DashboardResponse
from app.schemas.notification import ActivityOut
from app.services.dashboard import build_stats
from app.services.rbac import _ROLE_RANK
from app.services.search import allowed_departments

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(principal: CurrentPrincipal, db: DbSession) -> DashboardResponse:
    stats = await build_stats(db, principal)

    scope = [] if principal.is_admin else allowed_departments(principal)
    events, _ = await ActivityRepository(db).feed(scope, 0, 10)

    top_role = max(principal.roles, key=lambda r: _ROLE_RANK[r]) if principal.roles else None
    return DashboardResponse(
        department=principal.department,
        role_tier=top_role.value if top_role else "viewer",
        stats=stats,
        recent_activity=[ActivityOut.model_validate(e) for e in events],
    )
