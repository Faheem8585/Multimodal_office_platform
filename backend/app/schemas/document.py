"""Document schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Department, DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    filename: str
    content_type: str
    size_bytes: int
    department: Department
    status: DocumentStatus
    error: str | None = None
    doc_metadata: dict = {}
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentOut
    task_id: str | None = None
    message: str = "Document accepted; processing in background."
