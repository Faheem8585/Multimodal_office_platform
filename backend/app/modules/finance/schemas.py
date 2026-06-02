"""Finance module schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Department


class ExpenseCreate(BaseModel):
    merchant: str = Field(default="", max_length=255)
    category: str = Field(default="uncategorized", max_length=100)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    spent_on: date | None = None
    description: str = Field(default="", max_length=2000)
    receipt_document_id: uuid.UUID | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department: Department
    merchant: str
    category: str
    amount: Decimal
    currency: str
    spent_on: date | None = None
    description: str
    status: str
    receipt_document_id: uuid.UUID | None = None
    ocr_extracted: dict
    approval_request_id: uuid.UUID | None = None
    created_at: datetime


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=100)
    vendor_name: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    issue_date: date | None = None
    due_date: date | None = None
    document_id: uuid.UUID | None = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    vendor_name: str
    amount: Decimal
    currency: str
    issue_date: date | None = None
    due_date: date | None = None
    status: str
    document_id: uuid.UUID | None = None
    created_at: datetime


class BudgetCreate(BaseModel):
    department: Department
    fiscal_year: int = Field(ge=2000, le=2100)
    category: str = Field(default="general", max_length=100)
    allocated: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department: Department
    fiscal_year: int
    category: str
    allocated: Decimal
    spent: Decimal
    currency: str


class BudgetSummary(BaseModel):
    department: Department
    fiscal_year: int
    total_allocated: Decimal
    total_spent: Decimal
    remaining: Decimal
    utilization_pct: float
