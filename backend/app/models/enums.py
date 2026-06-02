"""Shared enumerations used across models and schemas."""

from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM as PgEnum


def native_enum(enum_cls: type[StrEnum], name: str) -> PgEnum:
    """Build a Postgres ENUM column type from a StrEnum.

    `values_callable` is the crucial bit: SQLAlchemy otherwise persists the enum
    *member name* (e.g. "ADMIN"), but our migrations create the PG type with the
    lowercase *values* (e.g. "admin"). Using the values keeps writes/reads valid.
    `create_type=False` because the migration owns type creation.
    """
    return PgEnum(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


class Department(StrEnum):
    HR = "hr"
    FINANCE = "finance"
    IT = "it"
    OPERATIONS = "operations"
    MARKETING = "marketing"
    LEGAL = "legal"
    PROCUREMENT = "procurement"


class RoleName(StrEnum):
    """Coarse RBAC tiers. Department scoping is enforced separately via the
    user's `department` plus per-resource ownership checks."""

    ADMIN = "admin"  # org-wide superuser
    DEPT_MANAGER = "dept_manager"  # manage within own department
    DEPT_MEMBER = "dept_member"  # operate within own department
    VIEWER = "viewer"  # read-only


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class StepDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
