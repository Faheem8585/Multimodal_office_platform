"""Approval engine schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ApprovalStatus, Department, RoleName, StepDecision


class WorkflowStepIn(BaseModel):
    order_index: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=200)
    required_role: RoleName
    required_department: Department | None = None


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    department: Department
    resource_type: str = Field(min_length=1, max_length=100)
    trigger: dict[str, Any] = Field(default_factory=dict)
    steps: list[WorkflowStepIn] = Field(min_length=1)


class WorkflowStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_index: int
    name: str
    required_role: RoleName
    required_department: Department | None = None


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    department: Department
    resource_type: str
    is_active: bool
    trigger: dict[str, Any]
    steps: list[WorkflowStepOut]


class StepInstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_index: int
    name: str
    required_role: RoleName
    required_department: Department | None = None
    decision: StepDecision
    decided_by: uuid.UUID | None = None
    comment: str | None = None


class ApprovalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: str
    resource_id: str
    department: Department
    status: ApprovalStatus
    current_step: int
    requested_by: uuid.UUID | None = None
    context: dict[str, Any]
    steps: list[StepInstanceOut]
    created_at: datetime


class DecisionIn(BaseModel):
    approve: bool
    comment: str | None = Field(default=None, max_length=2000)
