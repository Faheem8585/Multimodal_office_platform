"""Helpers to emit notifications and activity-feed events.

Thin wrappers so any service can record a user notification or a feed event
without repeating ORM boilerplate. Both just stage rows on the session; the
caller's request/transaction commits them.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department
from app.models.notification import ActivityEvent, Notification


async def notify(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    body: str = "",
    category: str = "info",
    link: str | None = None,
    data: dict | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        body=body,
        category=category,
        link=link,
        data=data or {},
    )
    session.add(notification)
    return notification


async def record_activity(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    verb: str,
    summary: str,
    department: Department | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> ActivityEvent:
    event = ActivityEvent(
        actor_id=actor_id,
        department=department,
        verb=verb,
        summary=summary,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    session.add(event)
    return event
