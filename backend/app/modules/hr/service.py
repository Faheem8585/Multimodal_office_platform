"""HR domain logic: employees, onboarding, leave (with approval integration).

Leave requests flow through the shared approval engine. We register a finalizer
for the "leave_request" resource type so that when an approval reaches a terminal
state the engine calls back here to update the leave record and deduct the
employee's balance — without the engine knowing anything about HR.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.approval import ApprovalRequest
from app.models.enums import ApprovalStatus
from app.modules.hr.models import Employee, LeaveRequest, OnboardingTask
from app.repositories.base import BaseRepository
from app.services import approvals

log = get_logger(__name__)

LEAVE_RESOURCE = "leave_request"


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee


class LeaveRepository(BaseRepository[LeaveRequest]):
    model = LeaveRequest


class OnboardingRepository(BaseRepository[OnboardingTask]):
    model = OnboardingTask


def business_days(start: date, end: date) -> int:
    """Inclusive working-day count (Mon–Fri) between two dates."""
    if end < start:
        raise ValueError("end_date before start_date")

    days = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


async def submit_leave(
    session: AsyncSession,
    *,
    employee: Employee,
    requester_id: uuid.UUID,
    leave_type: str,
    start_date: date,
    end_date: date,
    reason: str,
) -> LeaveRequest:
    days = business_days(start_date, end_date)
    leave = LeaveRequest(
        employee_id=employee.id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        days=days,
        reason=reason,
        status="pending",
    )
    session.add(leave)
    await session.flush()

    request = await approvals.start_approval(
        session,
        requester_id=requester_id,
        department=employee.department,
        resource_type=LEAVE_RESOURCE,
        resource_id=str(leave.id),
        context={"days": days, "leave_type": leave_type},
    )
    if request is not None:
        leave.approval_request_id = request.id
    await session.flush()
    return leave


@approvals.register_finalizer(LEAVE_RESOURCE)
async def _finalize_leave(session: AsyncSession, request: ApprovalRequest) -> None:
    leave = await LeaveRepository(session).get(uuid.UUID(request.resource_id))
    if leave is None:
        return
    if request.status == ApprovalStatus.APPROVED:
        leave.status = "approved"
        employee = await EmployeeRepository(session).get(leave.employee_id)
        if employee is not None and leave.leave_type == "vacation":
            employee.annual_leave_days = max(0, employee.annual_leave_days - leave.days)
    elif request.status == ApprovalStatus.REJECTED:
        leave.status = "rejected"
    await session.flush()
    log.info("leave_finalized", leave_id=str(leave.id), status=leave.status)
