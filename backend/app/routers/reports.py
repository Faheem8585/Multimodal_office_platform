"""Report export endpoints (XLSX/PDF) for expenses and budgets."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.deps import CurrentPrincipal, DbSession
from app.models.enums import Department
from app.modules.finance.models import Budget, Expense
from app.modules.finance.service import BudgetRepository, ExpenseRepository
from app.services import reports

router = APIRouter(prefix="/reports", tags=["reports"])

_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _render(fmt: str, title: str, headers: list[str], rows: list[list]) -> Response:
    if fmt == "xlsx":
        data = reports.to_xlsx(title, headers, rows)
    else:
        data = reports.to_pdf(title, headers, rows)
    return Response(
        content=data,
        media_type=_MEDIA[fmt],
        headers={"Content-Disposition": f'attachment; filename="{title}.{fmt}"'},
    )


@router.get("/expenses.{fmt}")
async def export_expenses(
    fmt: Literal["xlsx", "pdf"],
    principal: CurrentPrincipal,
    db: DbSession,
    department: Annotated[Department | None, Query()] = None,
) -> Response:
    if not (principal.is_admin or principal.department == Department.FINANCE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Finance access required")
    filters = [Expense.department == department] if department else None
    items, _ = await ExpenseRepository(db).list_page(0, 5000, filters=filters)
    headers = ["Date", "Merchant", "Category", "Amount", "Currency", "Status"]
    rows = [
        [
            e.spent_on.isoformat() if e.spent_on else "",
            e.merchant,
            e.category,
            f"{e.amount:.2f}",
            e.currency,
            e.status,
        ]
        for e in items
    ]
    return _render(fmt, "expenses", headers, rows)


@router.get("/budgets.{fmt}")
async def export_budgets(
    fmt: Literal["xlsx", "pdf"],
    principal: CurrentPrincipal,
    db: DbSession,
    fiscal_year: Annotated[int, Query(ge=2000, le=2100)],
) -> Response:
    dept = principal.department
    if principal.is_admin:
        filters = [Budget.fiscal_year == fiscal_year]
    else:
        filters = [Budget.fiscal_year == fiscal_year, Budget.department == dept]
    items, _ = await BudgetRepository(db).list_page(0, 5000, filters=filters)
    headers = ["Department", "Category", "Allocated", "Spent", "Remaining", "Currency"]
    rows = [
        [
            b.department.value,
            b.category,
            f"{b.allocated:.2f}",
            f"{b.spent:.2f}",
            f"{(b.allocated - b.spent):.2f}",
            b.currency,
        ]
        for b in items
    ]
    return _render(fmt, "budgets", headers, rows)
