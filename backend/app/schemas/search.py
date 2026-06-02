"""Search and chat schemas."""

import uuid

from pydantic import BaseModel, Field

from app.models.enums import Department


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    department: Department | None = None  # None => all departments caller may see
    limit: int = Field(default=8, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    department: Department
    top_k: int = Field(default=6, ge=1, le=20)


class ChatSource(BaseModel):
    document_id: uuid.UUID
    content: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
