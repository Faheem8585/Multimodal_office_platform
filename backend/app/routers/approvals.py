"""Approval engine endpoints: configure workflows, view + decide requests."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import CurrentPrincipal, DbSession, require_role
from app.models.approval import ApprovalWorkflow, ApprovalWorkflowStep
from app.models.enums import Department, RoleName
from app.repositories.approval import ApprovalRequestRepository, WorkflowRepository
from app.schemas.approval import (
    ApprovalRequestOut,
    DecisionIn,
    WorkflowCreate,
    WorkflowOut,
)
from app.services import approvals

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post(
    "/workflows",
    response_model=WorkflowOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleName.DEPT_MANAGER))],
)
async def create_workflow(
    body: WorkflowCreate, principal: CurrentPrincipal, db: DbSession
) -> WorkflowOut:
    if not principal.can_manage_department(body.department):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot configure this department")
    orders = [s.order_index for s in body.steps]
    if len(set(orders)) != len(orders):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate step order_index")

    workflow = ApprovalWorkflow(
        name=body.name,
        department=body.department,
        resource_type=body.resource_type,
        trigger=body.trigger,
        steps=[
            ApprovalWorkflowStep(
                order_index=s.order_index,
                name=s.name,
                required_role=s.required_role,
                required_department=s.required_department,
            )
            for s in body.steps
        ],
    )
    db.add(workflow)
    await db.flush()
    return WorkflowOut.model_validate(workflow)


@router.get(
    "/workflows",
    response_model=list[WorkflowOut],
    dependencies=[Depends(require_role(RoleName.DEPT_MANAGER))],
)
async def list_workflows(
    principal: CurrentPrincipal,
    db: DbSession,
    department: Department | None = None,
    resource_type: str | None = None,
) -> list[WorkflowOut]:
    dept = department or principal.department
    if not principal.can_manage_department(dept):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Outside your scope")
    repo = WorkflowRepository(db)
    if resource_type:
        workflows = await repo.active_for(dept, resource_type)
    else:
        items, _ = await repo.list_page(0, 100, filters=[ApprovalWorkflow.department == dept])
        workflows = items
    return [WorkflowOut.model_validate(w) for w in workflows]


@router.get("/requests/pending", response_model=list[ApprovalRequestOut])
async def pending_requests(principal: CurrentPrincipal, db: DbSession) -> list[ApprovalRequestOut]:
    requests = await ApprovalRequestRepository(db).pending_for_approver(
        role_names=principal.roles,
        department=principal.department,
        is_admin=principal.is_admin,
    )
    return [ApprovalRequestOut.model_validate(r) for r in requests]


@router.get("/requests/{request_id}", response_model=ApprovalRequestOut)
async def get_request(
    request_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> ApprovalRequestOut:
    request = await ApprovalRequestRepository(db).get_with_steps(request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if (
        not principal.can_access_department(request.department)
        and str(request.requested_by) != principal.user_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Outside your scope")
    return ApprovalRequestOut.model_validate(request)


@router.post("/requests/{request_id}/decide", response_model=ApprovalRequestOut)
async def decide_request(
    request_id: uuid.UUID,
    body: DecisionIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> ApprovalRequestOut:
    try:
        request = await approvals.decide(
            db,
            principal=principal,
            request_id=request_id,
            approve=body.approve,
            comment=body.comment,
        )
    except approvals.NotAuthorizedToDecide as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except approvals.ApprovalError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return ApprovalRequestOut.model_validate(request)
