"""Finance endpoints: expenses (with receipts), invoices, budgets.

Expenses are submitted by any user for their own department's budget; Finance
staff and admins oversee everything. Invoices and budgets are managed by Finance
staff/admins. Receipt OCR is handled by the document pipeline; an expense links
to its receipt Document and surfaces extracted fields.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import CurrentPrincipal, DbSession, require_role
from app.models.enums import Department, RoleName
from app.modules.finance import service
from app.modules.finance.models import Budget, Expense, Invoice
from app.modules.finance.schemas import (
    BudgetCreate,
    BudgetOut,
    BudgetSummary,
    ExpenseCreate,
    ExpenseOut,
    InvoiceCreate,
    InvoiceOut,
)
from app.schemas.common import Page, PageParams

router = APIRouter(prefix="/finance", tags=["finance"])


def _ensure_finance_staff(principal) -> None:  # type: ignore[no-untyped-def]
    if not (principal.is_admin or principal.department == Department.FINANCE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Finance access required")


# --- Expenses ---
@router.post(
    "/expenses",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleName.DEPT_MEMBER))],
)
async def create_expense(
    body: ExpenseCreate, principal: CurrentPrincipal, db: DbSession
) -> ExpenseOut:
    expense = Expense(
        submitted_by=uuid.UUID(principal.user_id),
        department=principal.department,
        status="draft",
        **body.model_dump(),
    )
    db.add(expense)
    await db.flush()
    return ExpenseOut.model_validate(expense)


@router.post("/expenses/{expense_id}/submit", response_model=ExpenseOut)
async def submit_expense(
    expense_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> ExpenseOut:
    repo = service.ExpenseRepository(db)
    expense = await repo.get(expense_id)
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    if str(expense.submitted_by) != principal.user_id and not principal.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your expense")
    if expense.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Expense already submitted")
    expense = await service.submit_expense(
        db, expense=expense, requester_id=uuid.UUID(principal.user_id)
    )
    return ExpenseOut.model_validate(expense)


@router.get("/expenses", response_model=Page[ExpenseOut])
async def list_expenses(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> Page[ExpenseOut]:
    filters = []
    if principal.is_admin or principal.department == Department.FINANCE:
        pass  # see all
    elif principal.has_at_least(RoleName.DEPT_MANAGER):
        filters.append(Expense.department == principal.department)
    else:
        filters.append(Expense.submitted_by == uuid.UUID(principal.user_id))
    if status_filter:
        filters.append(Expense.status == status_filter)
    items, total = await service.ExpenseRepository(db).list_page(
        params.offset, params.size, filters=filters or None
    )
    return Page(
        items=[ExpenseOut.model_validate(e) for e in items],
        total=total,
        page=params.page,
        size=params.size,
    )


# --- Invoices ---
@router.post(
    "/invoices",
    response_model=InvoiceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleName.DEPT_MEMBER))],
)
async def create_invoice(
    body: InvoiceCreate, principal: CurrentPrincipal, db: DbSession
) -> InvoiceOut:
    _ensure_finance_staff(principal)
    invoice = Invoice(status="received", **body.model_dump())
    db.add(invoice)
    await db.flush()
    return InvoiceOut.model_validate(invoice)


@router.get("/invoices", response_model=Page[InvoiceOut])
async def list_invoices(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
) -> Page[InvoiceOut]:
    _ensure_finance_staff(principal)
    items, total = await service.InvoiceRepository(db).list_page(params.offset, params.size)
    return Page(
        items=[InvoiceOut.model_validate(i) for i in items],
        total=total,
        page=params.page,
        size=params.size,
    )


# --- Budgets ---
@router.post(
    "/budgets",
    response_model=BudgetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RoleName.DEPT_MANAGER))],
)
async def create_budget(
    body: BudgetCreate, principal: CurrentPrincipal, db: DbSession
) -> BudgetOut:
    _ensure_finance_staff(principal)
    budget = Budget(**body.model_dump())
    db.add(budget)
    await db.flush()
    return BudgetOut.model_validate(budget)


@router.get("/budgets", response_model=Page[BudgetOut])
async def list_budgets(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    department: Annotated[Department | None, Query()] = None,
) -> Page[BudgetOut]:
    # Finance/admin see all departments' budgets; others only their own.
    if principal.is_admin or principal.department == Department.FINANCE:
        filters = [Budget.department == department] if department else None
    else:
        filters = [Budget.department == principal.department]
    items, total = await service.BudgetRepository(db).list_page(
        params.offset, params.size, filters=filters
    )
    return Page(
        items=[BudgetOut.model_validate(b) for b in items],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.get("/budgets/summary", response_model=BudgetSummary)
async def budget_summary(
    principal: CurrentPrincipal,
    db: DbSession,
    fiscal_year: Annotated[int, Query(ge=2000, le=2100)],
    department: Annotated[Department | None, Query()] = None,
) -> BudgetSummary:
    dept = department or principal.department
    if not principal.can_access_department(dept):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Outside your scope")
    items, _ = await service.BudgetRepository(db).list_page(
        0, 1000, filters=[Budget.department == dept, Budget.fiscal_year == fiscal_year]
    )
    allocated = sum((b.allocated for b in items), Decimal(0))
    spent = sum((b.spent for b in items), Decimal(0))
    remaining = allocated - spent
    util = float(spent / allocated * 100) if allocated else 0.0
    return BudgetSummary(
        department=dept,
        fiscal_year=fiscal_year,
        total_allocated=allocated,
        total_spent=spent,
        remaining=remaining,
        utilization_pct=round(util, 2),
    )
