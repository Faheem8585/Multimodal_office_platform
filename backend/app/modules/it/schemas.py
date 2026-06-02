"""IT module schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Department


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=8000)
    priority: str = Field(default="medium")


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assignee_id: uuid.UUID | None = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    status: str
    priority: str
    requester_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    requester_department: Department
    created_at: datetime


class AssetCreate(BaseModel):
    asset_tag: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="laptop", max_length=100)
    serial_number: str | None = Field(default=None, max_length=128)
    purchased_on: date | None = None
    warranty_until: date | None = None


class AssetUpdate(BaseModel):
    status: str | None = None
    assigned_to: uuid.UUID | None = None
    warranty_until: date | None = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_tag: str
    name: str
    category: str
    serial_number: str | None = None
    status: str
    assigned_to: uuid.UUID | None = None
    purchased_on: date | None = None
    warranty_until: date | None = None


class AccessRequestCreate(BaseModel):
    system: str = Field(min_length=1, max_length=200)
    access_level: str = Field(default="read", max_length=100)
    justification: str = Field(default="", max_length=2000)


class AccessRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    system: str
    access_level: str
    justification: str
    status: str
    approval_request_id: uuid.UUID | None = None
    created_at: datetime
