"""Document + chunk data access, including semantic and full-text search.

Semantic search uses pgvector cosine distance over chunk embeddings; full-text
search uses Postgres' GIN tsvector index over extracted document text. Both are
department-scoped at the query level so RBAC can't be bypassed by search.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text

from app.models.document import Document, DocumentChunk
from app.models.enums import Department
from app.repositories.base import BaseRepository


@dataclass
class ScoredChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float  # higher = more relevant


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def list_for_department(
        self, department: Department, offset: int, limit: int
    ) -> tuple[list[Document], int]:
        return await self.list_page(offset, limit, filters=[Document.department == department])

    async def semantic_search(
        self,
        query_embedding: list[float],
        departments: list[Department],
        limit: int = 8,
    ) -> list[ScoredChunk]:
        # Cosine distance in [0, 2]; convert to a similarity score in [-1, 1].
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.content,
                distance.label("distance"),
            )
            .where(DocumentChunk.department.in_(departments))
            .order_by(distance.asc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            ScoredChunk(
                chunk_id=r.id,
                document_id=r.document_id,
                content=r.content,
                score=1.0 - float(r.distance),
            )
            for r in rows
        ]

    async def fulltext_search(
        self, query: str, departments: list[Department], offset: int, limit: int
    ) -> tuple[list[Document], int]:
        ts_query = func.plainto_tsquery("english", query)
        ts_vector = func.to_tsvector("english", func.coalesce(Document.extracted_text, ""))
        base = select(Document).where(
            Document.department.in_(departments),
            Document.deleted_at.is_(None),
            ts_vector.op("@@")(ts_query),
        )
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        ranked = base.order_by(func.ts_rank(ts_vector, ts_query).desc()).offset(offset).limit(limit)
        items = list((await self.session.execute(ranked)).scalars().all())
        return items, total


class ChunkRepository(BaseRepository[DocumentChunk]):
    model = DocumentChunk

    async def delete_for_document(self, document_id: uuid.UUID) -> None:
        await self.session.execute(
            text("DELETE FROM document_chunks WHERE document_id = :id"),
            {"id": str(document_id)},
        )

    def bulk_add(self, chunks: list[DocumentChunk]) -> None:
        self.session.add_all(chunks)
