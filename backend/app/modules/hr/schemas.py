"""HR module schemas."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Department


class EmployeeCreate(BaseModel):
    employee_number: str = Field(min_length=1, max_length=32)
    full_name: str = Field(min_length=1, max_length=200)
    work_email: EmailStr
    job_title: str = Field(default="", max_length=200)
    department: Department
    manager_id: uuid.UUID | None = None
    hire_date: date | None = None
    annual_leave_days: int = Field(default=30, ge=0, le=365)
    user_id: uuid.UUID | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=200)
    manager_id: uuid.UUID | None = None
    annual_leave_days: int | None = Field(default=None, ge=0, le=365)


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_number: str
    full_name: str
    work_email: EmailStr
    job_title: str
    department: Department
    manager_id: uuid.UUID | None = None
    hire_date: date | None = None
    annual_leave_days: int
    created_at: datetime


class OnboardingTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    due_date: date | None = None


class OnboardingTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    title: str
    description: str
    completed: bool
    due_date: date | None = None


class LeaveRequestCreate(BaseModel):
    employee_id: uuid.UUID
    leave_type: str = Field(default="vacation")
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=2000)


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type: str
    start_date: date
    end_date: date
    days: int
    reason: str
    status: str
    approval_request_id: uuid.UUID | None = None
    created_at: datetime
