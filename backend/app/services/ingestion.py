"""Ingestion pipeline: extract -> chunk -> embed -> index.

Orchestrates the multimodal pipeline for a single document. Designed to be
idempotent: re-running on the same document replaces its chunks, so a retried
Celery job never produces duplicates. Status transitions
(uploaded -> processing -> indexed | failed) are persisted so the UI and ops can
see progress and failures.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document import DocumentChunk
from app.models.enums import DocumentStatus
from app.repositories.document import ChunkRepository, DocumentRepository
from app.services.chunking import chunk_text
from app.services.embeddings import Embedder, get_embedder
from app.services.extraction import extract
from app.services.storage import StorageBackend, get_storage

log = get_logger(__name__)

_EMBED_BATCH = 64


class IngestionError(Exception):
    pass


async def ingest_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    *,
    storage: StorageBackend | None = None,
    embedder: Embedder | None = None,
) -> int:
    """Process one document end to end. Returns the number of chunks indexed.

    Raises on failure (after recording status=failed) so the caller/Celery can
    apply retry-with-backoff.
    """
    storage = storage or get_storage()
    embedder = embedder or get_embedder()
    docs = DocumentRepository(session)
    chunks_repo = ChunkRepository(session)

    document = await docs.get(document_id)
    if document is None:
        raise IngestionError(f"document {document_id} not found")

    document.status = DocumentStatus.PROCESSING
    document.error = None
    await session.flush()

    try:
        raw = storage.get(document.storage_key)
        extraction = extract(raw, document.content_type, document.filename)
        document.extracted_text = extraction.text
        document.doc_metadata = {**(document.doc_metadata or {}), **extraction.metadata}

        pieces = chunk_text(extraction.text)
        # Idempotency: clear any prior chunks before re-indexing.
        await chunks_repo.delete_for_document(document_id)

        indexed = 0
        for start in range(0, len(pieces), _EMBED_BATCH):
            batch = pieces[start : start + _EMBED_BATCH]
            vectors = embedder.encode([c.content for c in batch])
            chunks_repo.bulk_add(
                [
                    DocumentChunk(
                        document_id=document.id,
                        department=document.department,
                        chunk_index=c.index,
                        content=c.content,
                        embedding=vec,
                    )
                    for c, vec in zip(batch, vectors, strict=True)
                ]
            )
            indexed += len(batch)
            await session.flush()

        document.status = DocumentStatus.INDEXED
        await session.flush()
        log.info("document_indexed", document_id=str(document_id), chunks=indexed)
        return indexed
    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.error = str(exc)[:2000]
        await session.flush()
        log.error("document_ingest_failed", document_id=str(document_id), error=str(exc))
        raise IngestionError(str(exc)) from exc
