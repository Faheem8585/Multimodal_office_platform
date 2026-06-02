"""HR endpoints: employee directory, onboarding, leave.

Access model: the employee directory and onboarding are managed by HR staff
(department == HR) or admins. Leave can be submitted by any user for their own
employee record; HR/admins can act on anyone's. Approvals route to the
employee's own department manager via the shared approval engine.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.deps import CurrentPrincipal, DbSession, require_role
from app.models.enums import Department, RoleName
from app.modules.hr import service
from app.modules.hr.models import Employee, OnboardingTask
from app.modules.hr.schemas import (
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    LeaveRequestCreate,
    LeaveRequestOut,
    OnboardingTaskCreate,
    OnboardingTaskOut,
)
from app.schemas.common import Page, PageParams

router = APIRouter(prefix="/hr", tags=["hr"])


def _ensure_hr_staff(principal) -> None:  # type: ignore[no-untyped-def]
    if not (principal.is_admin or principal.department == Department.HR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "HR access required")


# --- Employees ---
@router.post(
    "/employees",
    response_model=EmployeeOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleName.DEPT_MEMBER))],
)
async def create_employee(
    body: EmployeeCreate, principal: CurrentPrincipal, db: DbSession
) -> EmployeeOut:
    _ensure_hr_staff(principal)
    repo = service.EmployeeRepository(db)
    employee = Employee(**body.model_dump())
    repo.add(employee)
    await db.flush()
    return EmployeeOut.model_validate(employee)


@router.get("/employees", response_model=Page[EmployeeOut])
async def list_employees(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    department: Annotated[Department | None, Query()] = None,
) -> Page[EmployeeOut]:
    _ensure_hr_staff(principal)
    filters = [Employee.department == department] if department else None
    items, total = await service.EmployeeRepository(db).list_page(
        params.offset, params.size, filters=filters
    )
    return Page(
        items=[EmployeeOut.model_validate(e) for e in items],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> EmployeeOut:
    employee = await service.EmployeeRepository(db).get(employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    # HR/admin, or the employee viewing themselves.
    if not (
        principal.is_admin
        or principal.department == Department.HR
        or str(employee.user_id) == principal.user_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted")
    return EmployeeOut.model_validate(employee)


@router.patch(
    "/employees/{employee_id}",
    response_model=EmployeeOut,
    dependencies=[Depends(require_role(RoleName.DEPT_MANAGER))],
)
async def update_employee(
    employee_id: uuid.UUID,
    body: EmployeeUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> EmployeeOut:
    _ensure_hr_staff(principal)
    repo = service.EmployeeRepository(db)
    employee = await repo.get(employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(employee, key, value)
    await db.flush()
    return EmployeeOut.model_validate(employee)


@router.delete(
    "/employees/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(RoleName.DEPT_MANAGER))],
)
async def delete_employee(
    employee_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> Response:
    _ensure_hr_staff(principal)
    repo = service.EmployeeRepository(db)
    employee = await repo.get(employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    await repo.soft_delete(employee)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Onboarding ---
@router.post(
    "/employees/{employee_id}/onboarding",
    response_model=OnboardingTaskOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleName.DEPT_MEMBER))],
)
async def add_onboarding_task(
    employee_id: uuid.UUID,
    body: OnboardingTaskCreate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> OnboardingTaskOut:
    _ensure_hr_staff(principal)
    task = OnboardingTask(employee_id=employee_id, **body.model_dump())
    db.add(task)
    await db.flush()
    return OnboardingTaskOut.model_validate(task)


@router.get("/employees/{employee_id}/onboarding", response_model=list[OnboardingTaskOut])
async def list_onboarding(
    employee_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> list[OnboardingTaskOut]:
    _ensure_hr_staff(principal)
    items, _ = await service.OnboardingRepository(db).list_page(
        0, 100, filters=[OnboardingTask.employee_id == employee_id]
    )
    return [OnboardingTaskOut.model_validate(t) for t in items]


@router.patch("/onboarding/{task_id}", response_model=OnboardingTaskOut)
async def complete_onboarding_task(
    task_id: uuid.UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    completed: Annotated[bool, Query()] = True,
) -> OnboardingTaskOut:
    _ensure_hr_staff(principal)
    repo = service.OnboardingRepository(db)
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    task.completed = completed
    await db.flush()
    return OnboardingTaskOut.model_validate(task)


# --- Leave ---
@router.post("/leave", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
async def submit_leave(
    body: LeaveRequestCreate, principal: CurrentPrincipal, db: DbSession
) -> LeaveRequestOut:
    employee = await service.EmployeeRepository(db).get(body.employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    # Self-service, or HR/admin acting on behalf.
    if not (
        principal.is_admin
        or principal.department == Department.HR
        or str(employee.user_id) == principal.user_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Can only submit your own leave")
    try:
        leave = await service.submit_leave(
            db,
            employee=employee,
            requester_id=uuid.UUID(principal.user_id),
            leave_type=body.leave_type,
            start_date=body.start_date,
            end_date=body.end_date,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return LeaveRequestOut.model_validate(leave)


@router.get("/leave", response_model=Page[LeaveRequestOut])
async def list_leave(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[LeaveRequestOut]:
    from app.modules.hr.models import LeaveRequest

    filters = [LeaveRequest.employee_id == employee_id] if employee_id else None
    if not (principal.is_admin or principal.department == Department.HR):
        # Non-HR callers may only see their own leave.
        own = await service.EmployeeRepository(db).list_page(
            0, 1, filters=[Employee.user_id == uuid.UUID(principal.user_id)]
        )
        if not own[0]:
            return Page(items=[], total=0, page=params.page, size=params.size)
        filters = [LeaveRequest.employee_id == own[0][0].id]
    items, total = await service.LeaveRepository(db).list_page(
        params.offset, params.size, filters=filters
    )
    return Page(
        items=[LeaveRequestOut.model_validate(le) for le in items],
        total=total,
        page=params.page,
        size=params.size,
    )
