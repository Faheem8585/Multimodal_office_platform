"""HR module models: employee directory, onboarding, leave."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import Department
from app.models.user import department_enum

leave_status_enum = PgEnum(
    "pending", "approved", "rejected", "cancelled", name="leave_status", create_type=False
)
leave_type_enum = PgEnum(
    "vacation", "sick", "parental", "unpaid", "other", name="leave_type", create_type=False
)


class Employee(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """HR's record for a person; linked 1:1 to a login User when one exists."""

    __tablename__ = "hr_employees"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    employee_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    work_email: Mapped[str] = mapped_column(String(320), index=True)
    job_title: Mapped[str] = mapped_column(String(200), default="")
    department: Mapped[Department] = mapped_column(department_enum, index=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="SET NULL"), nullable=True
    )
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    annual_leave_days: Mapped[int] = mapped_column(Integer, default=30)

    onboarding_tasks: Mapped[list["OnboardingTask"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )


class OnboardingTask(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hr_onboarding_tasks"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    completed: Mapped[bool] = mapped_column(default=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    employee: Mapped[Employee] = relationship(back_populates="onboarding_tasks")


class LeaveRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hr_leave_requests"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="CASCADE"), index=True
    )
    leave_type: Mapped[str] = mapped_column(leave_type_enum, default="vacation")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(leave_status_enum, default="pending", index=True)
    # Links to a generic ApprovalRequest when the approval engine is used.
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    employee: Mapped[Employee] = relationship(back_populates="leave_requests")
