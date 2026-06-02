"""Notification + activity feed data access."""

import uuid

from sqlalchemy import select, update

from app.models.notification import ActivityEvent, Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_for_user(
        self, user_id: uuid.UUID, offset: int, limit: int, unread_only: bool
    ) -> tuple[list[Notification], int]:
        filters = [Notification.user_id == user_id]
        if unread_only:
            filters.append(Notification.read.is_(False))
        return await self.list_page(offset, limit, filters=filters)

    async def unread_count(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).where(
            Notification.user_id == user_id, Notification.read.is_(False)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(read=True)
        )

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read.is_(False))
            .values(read=True)
        )


class ActivityRepository(BaseRepository[ActivityEvent]):
    model = ActivityEvent

    async def feed(
        self, departments: list, offset: int, limit: int
    ) -> tuple[list[ActivityEvent], int]:
        filters = []
        if departments:
            filters.append(ActivityEvent.department.in_(departments))
        return await self.list_page(offset, limit, filters=filters)
