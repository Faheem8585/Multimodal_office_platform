"""Liveness and readiness probes.

/health is a cheap liveness check (process is up). /ready verifies critical
dependencies (DB, Redis) so orchestrators don't route traffic before we can
serve it. Kept out of the OpenAPI schema and unauthenticated by design.
"""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import engine

router = APIRouter(tags=["health"], include_in_schema=False)
log = get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    checks: dict[str, str] = {}
    ok = True

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - infra dependent
        checks["database"] = "error"
        ok = False
        log.error("readiness_db_failed", error=str(exc))

    try:
        import redis.asyncio as aioredis

        from app.core.config import settings

        client = aioredis.from_url(str(settings.redis_url))
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # pragma: no cover - infra dependent
        checks["redis"] = "error"
        ok = False
        log.error("readiness_redis_failed", error=str(exc))

    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ok else "degraded", **checks}
