"""IT domain logic: tickets, assets, access requests (approval-integrated).

Access requests always route through the approval engine (security-sensitive),
so if no workflow is configured the request stays pending rather than being
silently granted. The finalizer flips the request to approved/rejected once a
decision is made.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.approval import ApprovalRequest
from app.models.enums import ApprovalStatus, Department
from app.modules.it.models import AccessRequest, Asset, Ticket
from app.repositories.base import BaseRepository
from app.services import approvals

log = get_logger(__name__)

ACCESS_RESOURCE = "access_request"


class TicketRepository(BaseRepository[Ticket]):
    model = Ticket


class AssetRepository(BaseRepository[Asset]):
    model = Asset


class AccessRequestRepository(BaseRepository[AccessRequest]):
    model = AccessRequest


async def submit_access_request(
    session: AsyncSession,
    *,
    requester_id: uuid.UUID,
    system: str,
    access_level: str,
    justification: str,
) -> AccessRequest:
    access = AccessRequest(
        requester_id=requester_id,
        system=system,
        access_level=access_level,
        justification=justification,
        status="pending",
    )
    session.add(access)
    await session.flush()

    request = await approvals.start_approval(
        session,
        requester_id=requester_id,
        department=Department.IT,
        resource_type=ACCESS_RESOURCE,
        resource_id=str(access.id),
        context={"system": system, "access_level": access_level},
    )
    if request is not None:
        access.approval_request_id = request.id
    await session.flush()
    return access


@approvals.register_finalizer(ACCESS_RESOURCE)
async def _finalize_access(session: AsyncSession, request: ApprovalRequest) -> None:
    access = await AccessRequestRepository(session).get(uuid.UUID(request.resource_id))
    if access is None:
        return
    if request.status == ApprovalStatus.APPROVED:
        access.status = "approved"
    elif request.status == ApprovalStatus.REJECTED:
        access.status = "rejected"
    await session.flush()
    log.info("access_request_finalized", id=str(access.id), status=access.status)
