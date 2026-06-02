"""Identity and RBAC models: User, Role, and RefreshToken.

RBAC model: a User belongs to exactly one Department and holds one or more
Roles (coarse tiers). Authorization combines the role tier with the user's
department to produce department-scoped permissions (see services/rbac.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import Department, RoleName, native_enum

# Reusable PG enum types (created once in the migration). `native_enum` sets
# values_callable so SQLAlchemy persists the StrEnum *value* ("admin"), matching
# the lowercase values the migration creates — not the member name ("ADMIN").
department_enum = native_enum(Department, "department")
role_enum = native_enum(RoleName, "role_name")


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(255))
    department: Mapped[Department] = mapped_column(department_enum, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles", back_populates="users", lazy="selectin"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def role_names(self) -> set[RoleName]:
        return {r.name for r in self.roles}


class Role(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[RoleName] = mapped_column(role_enum, unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")

    users: Mapped[list[User]] = relationship(secondary="user_roles", back_populates="roles")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class RefreshToken(Base, UUIDMixin, TimestampMixin):
    """One row per issued refresh token (hashed). Supports rotation + reuse
    detection: when a token is used, it is marked `revoked` and a child is
    issued. If a revoked token is presented again, the whole family is
    revoked (see services/auth.py)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_refresh_token_hash"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, index=True)  # rotation lineage
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
