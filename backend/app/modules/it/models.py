"""IT module models: tickets, asset inventory, access requests."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import Department
from app.models.user import department_enum

ticket_status_enum = PgEnum(
    "open",
    "in_progress",
    "waiting",
    "resolved",
    "closed",
    name="ticket_status",
    create_type=False,
)
ticket_priority_enum = PgEnum(
    "low", "medium", "high", "critical", name="ticket_priority", create_type=False
)
asset_status_enum = PgEnum(
    "in_stock",
    "assigned",
    "maintenance",
    "retired",
    name="asset_status",
    create_type=False,
)
access_status_enum = PgEnum(
    "pending",
    "approved",
    "rejected",
    "revoked",
    name="access_status",
    create_type=False,
)


class Ticket(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "it_tickets"

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(ticket_status_enum, default="open", index=True)
    priority: Mapped[str] = mapped_column(ticket_priority_enum, default="medium", index=True)
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requester_department: Mapped[Department] = mapped_column(department_enum, index=True)


class Asset(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "it_assets"

    asset_tag: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), default="laptop")
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(asset_status_enum, default="in_stock", index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purchased_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_until: Mapped[date | None] = mapped_column(Date, nullable=True)


class AccessRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "it_access_requests"

    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    system: Mapped[str] = mapped_column(String(200))  # e.g. "VPN", "GitHub org"
    access_level: Mapped[str] = mapped_column(String(100), default="read")
    justification: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(access_status_enum, default="pending", index=True)
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
