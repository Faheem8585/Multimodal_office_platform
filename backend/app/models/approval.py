"""Configurable multi-step approval engine.

A *Workflow* is a reusable template (e.g. "expense > 1000€" needs manager then
finance). A *Request* is a running instance bound to any resource via
(resource_type, resource_id). Each *StepInstance* records one approver tier's
decision. The engine advances through ordered steps; any rejection ends it.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    ApprovalStatus,
    Department,
    RoleName,
    StepDecision,
    native_enum,
)
from app.models.user import department_enum, role_enum

approval_status_enum = native_enum(ApprovalStatus, "approval_status")
step_decision_enum = native_enum(StepDecision, "step_decision")


class ApprovalWorkflow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "approval_workflows"

    name: Mapped[str] = mapped_column(String(200))
    department: Mapped[Department] = mapped_column(department_enum, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Optional JSONLogic-style trigger, e.g. {">": [{"var": "amount"}, 1000]}.
    trigger: Mapped[dict] = mapped_column(JSONB, default=dict)

    steps: Mapped[list["ApprovalWorkflowStep"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="ApprovalWorkflowStep.order_index",
        lazy="selectin",
    )


class ApprovalWorkflowStep(Base, UUIDMixin):
    __tablename__ = "approval_workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "order_index", name="uq_workflow_step_order"),
    )

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_workflows.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    required_role: Mapped[RoleName] = mapped_column(role_enum)
    # If set, approver must be in this department; else the request's department.
    required_department: Mapped[Department | None] = mapped_column(department_enum, nullable=True)

    workflow: Mapped[ApprovalWorkflow] = relationship(back_populates="steps")


class ApprovalRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "approval_requests"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_workflows.id", ondelete="RESTRICT")
    )
    resource_type: Mapped[str] = mapped_column(String(100), index=True)
    resource_id: Mapped[str] = mapped_column(String(64), index=True)
    department: Mapped[Department] = mapped_column(department_enum, index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        approval_status_enum, default=ApprovalStatus.PENDING, index=True
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)  # trigger eval data

    steps: Mapped[list["ApprovalStepInstance"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="ApprovalStepInstance.order_index",
        lazy="selectin",
    )


class ApprovalStepInstance(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "approval_step_instances"

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    required_role: Mapped[RoleName] = mapped_column(role_enum)
    required_department: Mapped[Department | None] = mapped_column(department_enum, nullable=True)
    decision: Mapped[StepDecision] = mapped_column(step_decision_enum, default=StepDecision.PENDING)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped[ApprovalRequest] = relationship(back_populates="steps")
