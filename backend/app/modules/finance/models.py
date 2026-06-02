"""Finance module models: expenses (with receipts), invoices, budgets."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import Department
from app.models.user import department_enum

expense_status_enum = PgEnum(
    "draft",
    "submitted",
    "approved",
    "rejected",
    "reimbursed",
    name="expense_status",
    create_type=False,
)
invoice_status_enum = PgEnum(
    "received",
    "processing",
    "approved",
    "paid",
    "disputed",
    name="invoice_status",
    create_type=False,
)


class Expense(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "fin_expenses"

    submitted_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    department: Mapped[Department] = mapped_column(department_enum, index=True)
    merchant: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(100), default="uncategorized")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    spent_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(expense_status_enum, default="draft", index=True)
    # Receipt is a Document processed by OCR; extracted fields cached here.
    receipt_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    ocr_extracted: Mapped[dict] = mapped_column(JSONB, default=dict)
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class Invoice(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "fin_invoices"

    invoice_number: Mapped[str] = mapped_column(String(100), index=True)
    vendor_name: Mapped[str] = mapped_column(String(255), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(invoice_status_enum, default="received", index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    ocr_extracted: Mapped[dict] = mapped_column(JSONB, default=dict)


class Budget(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fin_budgets"

    department: Mapped[Department] = mapped_column(department_enum, index=True)
    fiscal_year: Mapped[int] = mapped_column()
    category: Mapped[str] = mapped_column(String(100), default="general")
    allocated: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    spent: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    expenses: Mapped[list[Expense]] = relationship(
        primaryjoin="and_(Budget.department==foreign(Expense.department))",
        viewonly=True,
    )
