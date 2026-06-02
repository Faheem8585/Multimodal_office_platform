"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- Enum type definitions (created explicitly; columns use create_type=False) ---
ENUMS: dict[str, tuple[str, ...]] = {
    "department": ("hr", "finance", "it", "operations", "marketing", "legal", "procurement"),
    "role_name": ("admin", "dept_manager", "dept_member", "viewer"),
    "document_status": ("uploaded", "processing", "indexed", "failed"),
    "approval_status": ("pending", "approved", "rejected", "cancelled"),
    "step_decision": ("pending", "approved", "rejected"),
    "leave_status": ("pending", "approved", "rejected", "cancelled"),
    "leave_type": ("vacation", "sick", "parental", "unpaid", "other"),
    "expense_status": ("draft", "submitted", "approved", "rejected", "reimbursed"),
    "invoice_status": ("received", "processing", "approved", "paid", "disputed"),
    "ticket_status": ("open", "in_progress", "waiting", "resolved", "closed"),
    "ticket_priority": ("low", "medium", "high", "critical"),
    "asset_status": ("in_stock", "assigned", "maintenance", "retired"),
    "access_status": ("pending", "approved", "rejected", "revoked"),
}


def _enum(name: str) -> pg.ENUM:
    return pg.ENUM(*ENUMS[name], name=name, create_type=False)


def _ts(col: str) -> sa.Column:
    return sa.Column(col, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for name, values in ENUMS.items():
        pg.ENUM(*values, name=name).create(bind, checkfirst=True)

    uuid_pk = lambda: sa.Column("id", pg.UUID(as_uuid=True), primary_key=True)  # noqa: E731

    # --- roles ---
    op.create_table(
        "roles",
        uuid_pk(),
        sa.Column("name", _enum("role_name"), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        _ts("created_at"), _ts("updated_at"),
    )

    # --- users ---
    op.create_table(
        "users",
        uuid_pk(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("department", _enum("department"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_department", "users", ["department"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    # --- user_roles (M2M) ---
    op.create_table(
        "user_roles",
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", pg.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        uuid_pk(),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("user_agent", sa.String(255), nullable=False, server_default=""),
        sa.Column("ip_address", sa.String(64), nullable=False, server_default=""),
        _ts("created_at"), _ts("updated_at"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_revoked", "refresh_tokens", ["revoked"])

    # --- documents ---
    op.create_table(
        "documents",
        uuid_pk(),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("department", _enum("department"), nullable=False),
        sa.Column("status", _enum("document_status"), nullable=False, server_default="uploaded"),
        sa.Column("extracted_text", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("doc_metadata", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("uploaded_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_documents_department", "documents", ["department"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])
    # Full-text search index over extracted text.
    op.execute(
        "CREATE INDEX ix_documents_fts ON documents "
        "USING gin (to_tsvector('english', coalesce(extracted_text, '')))"
    )

    # --- document_chunks (pgvector) ---
    op.create_table(
        "document_chunks",
        uuid_pk(),
        sa.Column("document_id", pg.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department", _enum("department"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_department", "document_chunks", ["department"])
    op.create_index(
        "ix_document_chunks_embedding", "document_chunks", ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        uuid_pk(),
        sa.Column("actor_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(64)),
        sa.Column("method", sa.String(10), nullable=False, server_default=""),
        sa.Column("path", sa.String(512), nullable=False, server_default=""),
        sa.Column("status_code", sa.Integer),
        sa.Column("ip_address", pg.INET),
        sa.Column("request_id", sa.String(64)),
        sa.Column("detail", pg.JSONB, nullable=False, server_default="{}"),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_created_action", "audit_logs", ["created_at", "action"])

    # --- notifications ---
    op.create_table(
        "notifications",
        uuid_pk(),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False, server_default=""),
        sa.Column("category", sa.String(50), nullable=False, server_default="info"),
        sa.Column("link", sa.String(512)),
        sa.Column("read", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("data", pg.JSONB, nullable=False, server_default="{}"),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_read", "notifications", ["read"])

    # --- activity_events ---
    op.create_table(
        "activity_events",
        uuid_pk(),
        sa.Column("actor_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("department", _enum("department")),
        sa.Column("verb", sa.String(100), nullable=False),
        sa.Column("summary", sa.String(512), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", sa.String(64)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_activity_events_department", "activity_events", ["department"])

    # --- approval engine ---
    op.create_table(
        "approval_workflows",
        uuid_pk(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("department", _enum("department"), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("trigger", pg.JSONB, nullable=False, server_default="{}"),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_approval_workflows_department", "approval_workflows", ["department"])
    op.create_index("ix_approval_workflows_resource_type", "approval_workflows", ["resource_type"])

    op.create_table(
        "approval_workflow_steps",
        uuid_pk(),
        sa.Column("workflow_id", pg.UUID(as_uuid=True), sa.ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("required_role", _enum("role_name"), nullable=False),
        sa.Column("required_department", _enum("department")),
        sa.UniqueConstraint("workflow_id", "order_index", name="uq_workflow_step_order"),
    )
    op.create_index("ix_approval_workflow_steps_workflow_id", "approval_workflow_steps", ["workflow_id"])

    op.create_table(
        "approval_requests",
        uuid_pk(),
        sa.Column("workflow_id", pg.UUID(as_uuid=True), sa.ForeignKey("approval_workflows.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("department", _enum("department"), nullable=False),
        sa.Column("requested_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", _enum("approval_status"), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="0"),
        sa.Column("context", pg.JSONB, nullable=False, server_default="{}"),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_approval_requests_resource_type", "approval_requests", ["resource_type"])
    op.create_index("ix_approval_requests_resource_id", "approval_requests", ["resource_id"])
    op.create_index("ix_approval_requests_department", "approval_requests", ["department"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    op.create_table(
        "approval_step_instances",
        uuid_pk(),
        sa.Column("request_id", pg.UUID(as_uuid=True), sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("required_role", _enum("role_name"), nullable=False),
        sa.Column("required_department", _enum("department")),
        sa.Column("decision", _enum("step_decision"), nullable=False, server_default="pending"),
        sa.Column("decided_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("comment", sa.Text),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_approval_step_instances_request_id", "approval_step_instances", ["request_id"])

    # --- HR module ---
    op.create_table(
        "hr_employees",
        uuid_pk(),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), unique=True),
        sa.Column("employee_number", sa.String(32), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("work_email", sa.String(320), nullable=False),
        sa.Column("job_title", sa.String(200), nullable=False, server_default=""),
        sa.Column("department", _enum("department"), nullable=False),
        sa.Column("manager_id", pg.UUID(as_uuid=True), sa.ForeignKey("hr_employees.id", ondelete="SET NULL")),
        sa.Column("hire_date", sa.Date),
        sa.Column("annual_leave_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_hr_employees_employee_number", "hr_employees", ["employee_number"], unique=True)
    op.create_index("ix_hr_employees_full_name", "hr_employees", ["full_name"])
    op.create_index("ix_hr_employees_work_email", "hr_employees", ["work_email"])
    op.create_index("ix_hr_employees_department", "hr_employees", ["department"])

    op.create_table(
        "hr_onboarding_tasks",
        uuid_pk(),
        sa.Column("employee_id", pg.UUID(as_uuid=True), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("completed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("due_date", sa.Date),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_hr_onboarding_tasks_employee_id", "hr_onboarding_tasks", ["employee_id"])

    op.create_table(
        "hr_leave_requests",
        uuid_pk(),
        sa.Column("employee_id", pg.UUID(as_uuid=True), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type", _enum("leave_type"), nullable=False, server_default="vacation"),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("days", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.Column("status", _enum("leave_status"), nullable=False, server_default="pending"),
        sa.Column("approval_request_id", pg.UUID(as_uuid=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_hr_leave_requests_employee_id", "hr_leave_requests", ["employee_id"])
    op.create_index("ix_hr_leave_requests_status", "hr_leave_requests", ["status"])

    # --- Finance module ---
    op.create_table(
        "fin_expenses",
        uuid_pk(),
        sa.Column("submitted_by", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("department", _enum("department"), nullable=False),
        sa.Column("merchant", sa.String(255), nullable=False, server_default=""),
        sa.Column("category", sa.String(100), nullable=False, server_default="uncategorized"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("spent_on", sa.Date),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("status", _enum("expense_status"), nullable=False, server_default="draft"),
        sa.Column("receipt_document_id", pg.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("ocr_extracted", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("approval_request_id", pg.UUID(as_uuid=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_fin_expenses_submitted_by", "fin_expenses", ["submitted_by"])
    op.create_index("ix_fin_expenses_department", "fin_expenses", ["department"])
    op.create_index("ix_fin_expenses_status", "fin_expenses", ["status"])

    op.create_table(
        "fin_invoices",
        uuid_pk(),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("issue_date", sa.Date),
        sa.Column("due_date", sa.Date),
        sa.Column("status", _enum("invoice_status"), nullable=False, server_default="received"),
        sa.Column("document_id", pg.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("ocr_extracted", pg.JSONB, nullable=False, server_default="{}"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_fin_invoices_invoice_number", "fin_invoices", ["invoice_number"])
    op.create_index("ix_fin_invoices_vendor_name", "fin_invoices", ["vendor_name"])
    op.create_index("ix_fin_invoices_due_date", "fin_invoices", ["due_date"])
    op.create_index("ix_fin_invoices_status", "fin_invoices", ["status"])

    op.create_table(
        "fin_budgets",
        uuid_pk(),
        sa.Column("department", _enum("department"), nullable=False),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("category", sa.String(100), nullable=False, server_default="general"),
        sa.Column("allocated", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("spent", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_fin_budgets_department", "fin_budgets", ["department"])

    # --- IT module ---
    op.create_table(
        "it_tickets",
        uuid_pk(),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("status", _enum("ticket_status"), nullable=False, server_default="open"),
        sa.Column("priority", _enum("ticket_priority"), nullable=False, server_default="medium"),
        sa.Column("requester_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("assignee_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("requester_department", _enum("department"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_it_tickets_status", "it_tickets", ["status"])
    op.create_index("ix_it_tickets_priority", "it_tickets", ["priority"])
    op.create_index("ix_it_tickets_requester_id", "it_tickets", ["requester_id"])
    op.create_index("ix_it_tickets_assignee_id", "it_tickets", ["assignee_id"])
    op.create_index("ix_it_tickets_requester_department", "it_tickets", ["requester_department"])

    op.create_table(
        "it_assets",
        uuid_pk(),
        sa.Column("asset_tag", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False, server_default="laptop"),
        sa.Column("serial_number", sa.String(128)),
        sa.Column("status", _enum("asset_status"), nullable=False, server_default="in_stock"),
        sa.Column("assigned_to", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("purchased_on", sa.Date),
        sa.Column("warranty_until", sa.Date),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_it_assets_asset_tag", "it_assets", ["asset_tag"], unique=True)
    op.create_index("ix_it_assets_status", "it_assets", ["status"])
    op.create_index("ix_it_assets_assigned_to", "it_assets", ["assigned_to"])

    op.create_table(
        "it_access_requests",
        uuid_pk(),
        sa.Column("requester_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("system", sa.String(200), nullable=False),
        sa.Column("access_level", sa.String(100), nullable=False, server_default="read"),
        sa.Column("justification", sa.Text, nullable=False, server_default=""),
        sa.Column("status", _enum("access_status"), nullable=False, server_default="pending"),
        sa.Column("approval_request_id", pg.UUID(as_uuid=True)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_it_access_requests_requester_id", "it_access_requests", ["requester_id"])
    op.create_index("ix_it_access_requests_status", "it_access_requests", ["status"])


def downgrade() -> None:
    for table in (
        "it_access_requests", "it_assets", "it_tickets",
        "fin_budgets", "fin_invoices", "fin_expenses",
        "hr_leave_requests", "hr_onboarding_tasks", "hr_employees",
        "approval_step_instances", "approval_requests",
        "approval_workflow_steps", "approval_workflows",
        "activity_events", "notifications", "audit_logs",
        "document_chunks", "documents",
        "refresh_tokens", "user_roles", "users", "roles",
    ):
        op.drop_table(table)
    bind = op.get_bind()
    for name in ENUMS:
        pg.ENUM(name=name).drop(bind, checkfirst=True)
