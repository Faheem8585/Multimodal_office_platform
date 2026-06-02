"""Notification + activity feed endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentPrincipal, DbSession
from app.repositories.notification import ActivityRepository, NotificationRepository
from app.schemas.common import Page, PageParams
from app.schemas.notification import ActivityOut, NotificationOut
from app.services.search import allowed_departments

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=Page[NotificationOut])
async def list_notifications(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    unread_only: Annotated[bool, Query()] = False,
) -> Page[NotificationOut]:
    items, total = await NotificationRepository(db).list_for_user(
        uuid.UUID(principal.user_id), params.offset, params.size, unread_only
    )
    return Page(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.get("/notifications/unread-count")
async def unread_count(principal: CurrentPrincipal, db: DbSession) -> dict[str, int]:
    count = await NotificationRepository(db).unread_count(uuid.UUID(principal.user_id))
    return {"unread": count}


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> Response:
    await NotificationRepository(db).mark_read(uuid.UUID(principal.user_id), notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(principal: CurrentPrincipal, db: DbSession) -> Response:
    await NotificationRepository(db).mark_all_read(uuid.UUID(principal.user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/activity", response_model=Page[ActivityOut])
async def activity_feed(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
) -> Page[ActivityOut]:
    # Admins see all departments; others see their own department's feed.
    depts = allowed_departments(principal)
    scope = [] if principal.is_admin else depts
    items, total = await ActivityRepository(db).feed(scope, params.offset, params.size)
    return Page(
        items=[ActivityOut.model_validate(a) for a in items],
        total=total,
        page=params.page,
        size=params.size,
    )
