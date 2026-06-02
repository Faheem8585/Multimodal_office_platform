"""Finance domain logic: expense submission/approval, budget rollups.

Expenses use the approval engine with an amount-based trigger: small expenses
fall through (no matching workflow) and are auto-approved; expenses over the
configured threshold require sign-off. On approval, the matching budget's spent
amount is incremented so dashboards stay accurate.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.approval import ApprovalRequest
from app.models.enums import ApprovalStatus
from app.modules.finance.models import Budget, Expense, Invoice
from app.repositories.base import BaseRepository
from app.services import approvals

log = get_logger(__name__)

EXPENSE_RESOURCE = "expense"


class ExpenseRepository(BaseRepository[Expense]):
    model = Expense


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice


class BudgetRepository(BaseRepository[Budget]):
    model = Budget


async def submit_expense(
    session: AsyncSession, *, expense: Expense, requester_id: uuid.UUID
) -> Expense:
    """Move a draft expense to submitted, starting approval if a workflow
    applies. If none applies (e.g. under threshold) it is auto-approved."""
    expense.status = "submitted"
    await session.flush()

    request = await approvals.start_approval(
        session,
        requester_id=requester_id,
        department=expense.department,
        resource_type=EXPENSE_RESOURCE,
        resource_id=str(expense.id),
        context={"amount": float(expense.amount), "category": expense.category},
    )
    if request is None:
        # No approval required — auto-approve and book against the budget.
        expense.status = "approved"
        await _apply_to_budget(session, expense)
    else:
        expense.approval_request_id = request.id
    await session.flush()
    return expense


@approvals.register_finalizer(EXPENSE_RESOURCE)
async def _finalize_expense(session: AsyncSession, request: ApprovalRequest) -> None:
    expense = await ExpenseRepository(session).get(uuid.UUID(request.resource_id))
    if expense is None:
        return
    if request.status == ApprovalStatus.APPROVED:
        expense.status = "approved"
        await _apply_to_budget(session, expense)
    elif request.status == ApprovalStatus.REJECTED:
        expense.status = "rejected"
    await session.flush()
    log.info("expense_finalized", expense_id=str(expense.id), status=expense.status)


async def _apply_to_budget(session: AsyncSession, expense: Expense) -> None:
    """Increment the department/category budget's spent figure if one exists."""
    from datetime import date

    fy = (expense.spent_on or date.today()).year
    stmt = select(Budget).where(
        Budget.department == expense.department,
        Budget.fiscal_year == fy,
        Budget.category == expense.category,
    )
    budget = (await session.execute(stmt)).scalar_one_or_none()
    if budget is None:
        # Fall back to the department's general budget for this year.
        stmt = select(Budget).where(
            Budget.department == expense.department,
            Budget.fiscal_year == fy,
            Budget.category == "general",
        )
        budget = (await session.execute(stmt)).scalar_one_or_none()
    if budget is not None:
        budget.spent = (budget.spent or Decimal(0)) + expense.amount
