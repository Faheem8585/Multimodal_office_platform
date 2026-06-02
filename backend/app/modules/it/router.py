"""IT endpoints: ticketing, asset inventory, access requests.

Any user can raise a ticket or access request; IT staff/admins triage tickets,
manage assets, and (with managers) approve access. Non-IT users see only their
own tickets and access requests.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import CurrentPrincipal, DbSession, require_role
from app.models.enums import Department, RoleName
from app.modules.it import service
from app.modules.it.models import AccessRequest, Asset, Ticket
from app.modules.it.schemas import (
    AccessRequestCreate,
    AccessRequestOut,
    AssetCreate,
    AssetOut,
    AssetUpdate,
    TicketCreate,
    TicketOut,
    TicketUpdate,
)
from app.schemas.common import Page, PageParams

router = APIRouter(prefix="/it", tags=["it"])


def _is_it_staff(principal) -> bool:  # type: ignore[no-untyped-def]
    return principal.is_admin or principal.department == Department.IT


def _ensure_it_staff(principal) -> None:  # type: ignore[no-untyped-def]
    if not _is_it_staff(principal):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "IT access required")


# --- Tickets ---
@router.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate, principal: CurrentPrincipal, db: DbSession
) -> TicketOut:
    ticket = Ticket(
        title=body.title,
        description=body.description,
        priority=body.priority,
        requester_id=uuid.UUID(principal.user_id),
        requester_department=principal.department,
        status="open",
    )
    db.add(ticket)
    await db.flush()
    return TicketOut.model_validate(ticket)


@router.get("/tickets", response_model=Page[TicketOut])
async def list_tickets(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> Page[TicketOut]:
    filters = []
    if not _is_it_staff(principal):
        filters.append(Ticket.requester_id == uuid.UUID(principal.user_id))
    if status_filter:
        filters.append(Ticket.status == status_filter)
    items, total = await service.TicketRepository(db).list_page(
        params.offset, params.size, filters=filters or None
    )
    return Page(
        items=[TicketOut.model_validate(t) for t in items],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: uuid.UUID,
    body: TicketUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> TicketOut:
    repo = service.TicketRepository(db)
    ticket = await repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    # Requester may only close their own ticket; IT staff can do anything.
    if not _is_it_staff(principal):
        if str(ticket.requester_id) != principal.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your ticket")
        if body.assignee_id is not None or body.priority is not None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only IT can triage")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(ticket, key, value)
    await db.flush()
    return TicketOut.model_validate(ticket)


# --- Assets ---
@router.post(
    "/assets",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleName.DEPT_MEMBER))],
)
async def create_asset(body: AssetCreate, principal: CurrentPrincipal, db: DbSession) -> AssetOut:
    _ensure_it_staff(principal)
    asset = Asset(status="in_stock", **body.model_dump())
    db.add(asset)
    await db.flush()
    return AssetOut.model_validate(asset)


@router.get("/assets", response_model=Page[AssetOut])
async def list_assets(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> Page[AssetOut]:
    _ensure_it_staff(principal)
    filters = [Asset.status == status_filter] if status_filter else None
    items, total = await service.AssetRepository(db).list_page(
        params.offset, params.size, filters=filters
    )
    return Page(
        items=[AssetOut.model_validate(a) for a in items],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.patch(
    "/assets/{asset_id}",
    response_model=AssetOut,
    dependencies=[Depends(require_role(RoleName.DEPT_MEMBER))],
)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> AssetOut:
    _ensure_it_staff(principal)
    repo = service.AssetRepository(db)
    asset = await repo.get(asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    await db.flush()
    return AssetOut.model_validate(asset)


# --- Access requests ---
@router.post(
    "/access-requests",
    response_model=AccessRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_access_request(
    body: AccessRequestCreate, principal: CurrentPrincipal, db: DbSession
) -> AccessRequestOut:
    access = await service.submit_access_request(
        db,
        requester_id=uuid.UUID(principal.user_id),
        system=body.system,
        access_level=body.access_level,
        justification=body.justification,
    )
    return AccessRequestOut.model_validate(access)


@router.get("/access-requests", response_model=Page[AccessRequestOut])
async def list_access_requests(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
) -> Page[AccessRequestOut]:
    filters = None
    if not _is_it_staff(principal):
        filters = [AccessRequest.requester_id == uuid.UUID(principal.user_id)]
    items, total = await service.AccessRequestRepository(db).list_page(
        params.offset, params.size, filters=filters
    )
    return Page(
        items=[AccessRequestOut.model_validate(a) for a in items],
        total=total,
        page=params.page,
        size=params.size,
    )
