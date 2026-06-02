"""Role-aware dashboard aggregation.

Builds a set of stat cards tailored to the caller's department and role tier,
plus a slice of the activity feed. Counts use lightweight COUNT queries rather
than loading rows. Cards always include the cross-cutting items (pending
approvals, unread notifications); department-specific cards are added on top.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department
from app.models.notification import Notification
from app.modules.finance.models import Budget, Expense
from app.modules.hr.models import Employee, LeaveRequest
from app.modules.it.models import AccessRequest, Asset, Ticket
from app.repositories.approval import ApprovalRequestRepository
from app.schemas.dashboard import StatCard
from app.services.rbac import Principal


async def _count(session: AsyncSession, stmt: Select) -> int:
    return (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()


async def build_stats(session: AsyncSession, principal: Principal) -> list[StatCard]:
    cards: list[StatCard] = []
    user_id = uuid.UUID(principal.user_id)

    # Cross-cutting cards for everyone.
    pending = await ApprovalRequestRepository(session).pending_for_approver(
        role_names=principal.roles,
        department=principal.department,
        is_admin=principal.is_admin,
    )
    cards.append(
        StatCard(
            key="pending_approvals",
            label="Approvals awaiting you",
            value=len(pending),
            link="/approvals",
        )
    )
    unread = await _count(
        session,
        select(Notification.id).where(
            Notification.user_id == user_id, Notification.read.is_(False)
        ),
    )
    cards.append(StatCard(key="unread_notifications", label="Unread notifications", value=unread))

    # Department-specific cards.
    dept = principal.department
    if dept == Department.HR or principal.is_admin:
        cards.extend(await _hr_cards(session))
    if dept == Department.FINANCE or principal.is_admin:
        cards.extend(await _finance_cards(session))
    if dept == Department.IT or principal.is_admin:
        cards.extend(await _it_cards(session))

    return cards


async def _hr_cards(session: AsyncSession) -> list[StatCard]:
    employees = await _count(session, select(Employee.id).where(Employee.deleted_at.is_(None)))
    pending_leave = await _count(
        session, select(LeaveRequest.id).where(LeaveRequest.status == "pending")
    )
    return [
        StatCard(
            key="hr_employees", label="Active employees", value=employees, link="/hr/employees"
        ),
        StatCard(
            key="hr_pending_leave",
            label="Leave requests pending",
            value=pending_leave,
            link="/hr/leave",
        ),
    ]


async def _finance_cards(session: AsyncSession) -> list[StatCard]:
    submitted = await _count(session, select(Expense.id).where(Expense.status == "submitted"))
    allocated = (
        await session.execute(select(func.coalesce(func.sum(Budget.allocated), 0)))
    ).scalar_one() or Decimal(0)
    spent = (
        await session.execute(select(func.coalesce(func.sum(Budget.spent), 0)))
    ).scalar_one() or Decimal(0)
    util = float(spent / allocated * 100) if allocated else 0.0
    return [
        StatCard(
            key="fin_expenses_pending",
            label="Expenses to review",
            value=submitted,
            link="/finance/expenses",
        ),
        StatCard(
            key="fin_budget_util",
            label="Budget utilization",
            value=round(util, 1),
            unit="%",
            link="/finance/budgets",
        ),
    ]


async def _it_cards(session: AsyncSession) -> list[StatCard]:
    open_tickets = await _count(
        session,
        select(Ticket.id).where(
            Ticket.status.in_(["open", "in_progress"]), Ticket.deleted_at.is_(None)
        ),
    )
    assigned_assets = await _count(session, select(Asset.id).where(Asset.status == "assigned"))
    pending_access = await _count(
        session, select(AccessRequest.id).where(AccessRequest.status == "pending")
    )
    return [
        StatCard(
            key="it_open_tickets", label="Open tickets", value=open_tickets, link="/it/tickets"
        ),
        StatCard(
            key="it_assigned_assets",
            label="Assigned assets",
            value=assigned_assets,
            link="/it/assets",
        ),
        StatCard(
            key="it_pending_access",
            label="Access requests pending",
            value=pending_access,
            link="/it/access-requests",
        ),
    ]
