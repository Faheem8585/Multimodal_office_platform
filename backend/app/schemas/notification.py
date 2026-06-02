"""Notification + activity feed schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Department


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    body: str
    category: str
    link: str | None = None
    read: bool
    data: dict
    created_at: datetime


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    department: Department | None = None
    verb: str
    summary: str
    resource_type: str | None = None
    resource_id: str | None = None
    created_at: datetime
