"""Generic async repository: typed CRUD, soft-delete awareness, pagination.

Repositories own data access so services stay free of SQLAlchemy specifics and
tests can swap them. Keeping queries here also centralises the soft-delete
filter, so we never accidentally return deleted rows.
"""

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_select(self, include_deleted: bool = False) -> Select:
        stmt = select(self.model)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    async def get(self, id_: uuid.UUID, include_deleted: bool = False) -> ModelT | None:
        stmt = self._base_select(include_deleted).where(self.model.id == id_)  # type: ignore[attr-defined]
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        offset: int,
        limit: int,
        filters: list[Any] | None = None,
        order_by: Any | None = None,
    ) -> tuple[list[ModelT], int]:
        stmt = self._base_select()
        if filters:
            stmt = stmt.where(*filters)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(self.model.created_at.desc())  # type: ignore[attr-defined]
        stmt = stmt.offset(offset).limit(limit)
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        return obj

    async def soft_delete(self, obj: ModelT) -> None:
        from datetime import UTC, datetime

        if hasattr(obj, "deleted_at"):
            obj.deleted_at = datetime.now(UTC)
        else:
            await self.session.delete(obj)

    async def flush(self) -> None:
        await self.session.flush()
