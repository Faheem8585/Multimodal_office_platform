"""Import all models so SQLAlchemy's metadata and Alembic see every table."""

from app.db.base import Base
from app.models.approval import (
    ApprovalRequest,
    ApprovalStepInstance,
    ApprovalWorkflow,
    ApprovalWorkflowStep,
)
from app.models.audit import AuditLog
from app.models.document import Document, DocumentChunk
from app.models.notification import ActivityEvent, Notification
from app.models.user import RefreshToken, Role, User, UserRole

# Department module tables.
from app.modules.finance.models import Budget, Expense, Invoice
from app.modules.hr.models import Employee, LeaveRequest, OnboardingTask
from app.modules.it.models import AccessRequest, Asset, Ticket

__all__ = [
    "Base",
    "User",
    "Role",
    "UserRole",
    "RefreshToken",
    "Document",
    "DocumentChunk",
    "AuditLog",
    "Notification",
    "ActivityEvent",
    "ApprovalWorkflow",
    "ApprovalWorkflowStep",
    "ApprovalRequest",
    "ApprovalStepInstance",
    "Employee",
    "OnboardingTask",
    "LeaveRequest",
    "Expense",
    "Invoice",
    "Budget",
    "Ticket",
    "Asset",
    "AccessRequest",
]
