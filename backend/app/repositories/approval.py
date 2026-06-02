"""Approval workflow + request data access."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.approval import ApprovalRequest, ApprovalWorkflow
from app.models.enums import ApprovalStatus, Department, RoleName
from app.repositories.base import BaseRepository


class WorkflowRepository(BaseRepository[ApprovalWorkflow]):
    model = ApprovalWorkflow

    async def active_for(
        self, department: Department, resource_type: str
    ) -> list[ApprovalWorkflow]:
        stmt = (
            select(ApprovalWorkflow)
            .where(
                ApprovalWorkflow.department == department,
                ApprovalWorkflow.resource_type == resource_type,
                ApprovalWorkflow.is_active.is_(True),
            )
            .options(selectinload(ApprovalWorkflow.steps))
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    model = ApprovalRequest

    async def get_with_steps(self, request_id: uuid.UUID) -> ApprovalRequest | None:
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.id == request_id)
            .options(selectinload(ApprovalRequest.steps))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def pending_for_approver(
        self,
        *,
        role_names: frozenset[RoleName],
        department: Department,
        is_admin: bool,
    ) -> list[ApprovalRequest]:
        """Requests whose *current* step this approver is eligible to decide."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.PENDING)
            .options(selectinload(ApprovalRequest.steps))
            .order_by(ApprovalRequest.created_at.asc())
        )
        if not is_admin:
            stmt = stmt.where(ApprovalRequest.department == department)
        requests = list((await self.session.execute(stmt)).scalars().all())

        eligible: list[ApprovalRequest] = []
        for req in requests:
            step = next((s for s in req.steps if s.order_index == req.current_step), None)
            if step is None:
                continue
            if is_admin or step.required_role in role_names:
                eligible.append(req)
        return eligible
