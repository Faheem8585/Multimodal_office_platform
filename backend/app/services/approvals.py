"""Configurable multi-step approval engine.

Lifecycle:
  start_approval() picks the first active workflow for (department, resource_type)
  whose declarative trigger matches the context, then instantiates an ordered
  set of step instances. decide() records one approver's decision, advancing to
  the next step on approval or terminating on rejection / final approval.

Extensibility: modules register a *finalizer* for their resource_type (e.g.
"leave_request") so the engine can apply the side effect (mark the leave
approved) without the engine importing module code — keeping modules pluggable.

Concurrency: decide() locks the request row (SELECT ... FOR UPDATE) so two
approvers acting at once can't double-advance or corrupt the step pointer.
"""

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.approval import (
    ApprovalRequest,
    ApprovalStepInstance,
    ApprovalWorkflow,
)
from app.models.enums import ApprovalStatus, Department, StepDecision
from app.repositories.approval import ApprovalRequestRepository, WorkflowRepository
from app.repositories.user import UserRepository
from app.services import notifications
from app.services.conditions import evaluate
from app.services.rbac import Principal

log = get_logger(__name__)

Finalizer = Callable[[AsyncSession, ApprovalRequest], Awaitable[None]]
_FINALIZERS: dict[str, Finalizer] = {}


def register_finalizer(resource_type: str) -> Callable[[Finalizer], Finalizer]:
    """Decorator: register a side-effect to run when a request for this
    resource_type reaches a terminal state (approved/rejected)."""

    def _wrap(fn: Finalizer) -> Finalizer:
        _FINALIZERS[resource_type] = fn
        return fn

    return _wrap


class ApprovalError(Exception):
    pass


class NotAuthorizedToDecide(ApprovalError):
    pass


def _instantiate_steps(workflow: ApprovalWorkflow) -> list[ApprovalStepInstance]:
    return [
        ApprovalStepInstance(
            order_index=s.order_index,
            name=s.name,
            required_role=s.required_role,
            required_department=s.required_department,
            decision=StepDecision.PENDING,
        )
        for s in sorted(workflow.steps, key=lambda s: s.order_index)
    ]


async def start_approval(
    session: AsyncSession,
    *,
    requester_id: uuid.UUID,
    department: Department,
    resource_type: str,
    resource_id: str,
    context: dict | None = None,
) -> ApprovalRequest | None:
    """Create a pending approval request, or None if no workflow applies
    (caller should treat None as 'no approval required')."""
    context = context or {}
    workflows = await WorkflowRepository(session).active_for(department, resource_type)
    workflow = next((w for w in workflows if evaluate(w.trigger, context)), None)
    if workflow is None or not workflow.steps:
        return None

    steps = _instantiate_steps(workflow)
    request = ApprovalRequest(
        workflow_id=workflow.id,
        resource_type=resource_type,
        resource_id=resource_id,
        department=department,
        requested_by=requester_id,
        status=ApprovalStatus.PENDING,
        current_step=steps[0].order_index,
        context=context,
        steps=steps,
    )
    session.add(request)
    await session.flush()
    await _notify_step_approvers(session, request)
    await notifications.record_activity(
        session,
        actor_id=requester_id,
        verb="requested_approval",
        summary=f"Approval requested for {resource_type}",
        department=department,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return request


async def decide(
    session: AsyncSession,
    *,
    principal: Principal,
    request_id: uuid.UUID,
    approve: bool,
    comment: str | None = None,
) -> ApprovalRequest:
    # Lock the request row to serialise concurrent decisions.
    locked = (
        await session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id).with_for_update()
        )
    ).scalar_one_or_none()
    if locked is None:
        raise ApprovalError("approval request not found")

    request = await ApprovalRequestRepository(session).get_with_steps(request_id)
    assert request is not None  # just locked it
    if request.status != ApprovalStatus.PENDING:
        raise ApprovalError(f"request already {request.status.value}")

    step = next((s for s in request.steps if s.order_index == request.current_step), None)
    if step is None:
        raise ApprovalError("no active step")

    if not _can_decide(principal, request, step):
        raise NotAuthorizedToDecide("you are not an eligible approver for this step")

    step.decided_by = uuid.UUID(principal.user_id)
    step.comment = comment
    step.decision = StepDecision.APPROVED if approve else StepDecision.REJECTED

    if not approve:
        request.status = ApprovalStatus.REJECTED
        await _finalize(session, request)
        return request

    # Approved: advance to the next step (by order), or finish.
    remaining = sorted(
        (s for s in request.steps if s.order_index > step.order_index),
        key=lambda s: s.order_index,
    )
    if remaining:
        request.current_step = remaining[0].order_index
        await session.flush()
        await _notify_step_approvers(session, request)
    else:
        request.status = ApprovalStatus.APPROVED
        await _finalize(session, request)
    return request


def _can_decide(principal: Principal, request: ApprovalRequest, step: ApprovalStepInstance) -> bool:
    if principal.is_admin:
        return True
    required_dept = step.required_department or request.department
    if principal.department != required_dept:
        return False
    return principal.has_at_least(step.required_role)


async def _finalize(session: AsyncSession, request: ApprovalRequest) -> None:
    finalizer = _FINALIZERS.get(request.resource_type)
    if finalizer is not None:
        await finalizer(session, request)
    await session.flush()

    if request.requested_by:
        await notifications.notify(
            session,
            user_id=request.requested_by,
            title=f"Your {request.resource_type.replace('_', ' ')} was {request.status.value}",
            category="approval",
            data={"request_id": str(request.id), "status": request.status.value},
        )
    await notifications.record_activity(
        session,
        actor_id=None,
        verb=request.status.value,
        summary=f"{request.resource_type} {request.status.value}",
        department=request.department,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
    )
    log.info(
        "approval_finalized",
        request_id=str(request.id),
        status=request.status.value,
        resource_type=request.resource_type,
    )


async def _notify_step_approvers(session: AsyncSession, request: ApprovalRequest) -> None:
    step = next((s for s in request.steps if s.order_index == request.current_step), None)
    if step is None:
        return
    dept = step.required_department or request.department
    approvers = await UserRepository(session).users_with_role(dept, step.required_role)
    for user in approvers:
        await notifications.notify(
            session,
            user_id=user.id,
            title="Approval needed",
            body=f"A {request.resource_type.replace('_', ' ')} awaits your approval.",
            category="approval",
            data={"request_id": str(request.id), "step": step.name},
        )
