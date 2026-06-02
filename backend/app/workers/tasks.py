"""Celery tasks. Bridges sync Celery to our async data layer.

Each task runs its own event loop with a dedicated engine/session, avoiding the
cross-event-loop pitfalls of sharing the API's asyncpg pool with workers.
Ingestion uses autoretry with exponential backoff + jitter for transient
failures (storage hiccups, DB blips).
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ingestion import ingest_document
from app.workers.celery_app import celery_app

log = get_logger(__name__)


async def _ingest(document_id: str) -> int:
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True, pool_size=2)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                count = await ingest_document(session, uuid.UUID(document_id))
                await session.commit()
                return count
            except Exception:
                await session.commit()  # persist the status=failed record
                raise
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    name="ingest_document",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=4,
)
def ingest_document_task(self, document_id: str) -> int:  # type: ignore[no-untyped-def]
    log.info("ingest_task_started", document_id=document_id, attempt=self.request.retries)
    return asyncio.run(_ingest(document_id))
