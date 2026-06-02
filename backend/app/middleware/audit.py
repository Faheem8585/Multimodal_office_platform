"""Audit middleware: persist an append-only record of every mutating request.

Writes go through an independent DB session so the audit row survives even if
the request's own transaction rolled back (e.g. a failed sensitive action is
still worth recording). Read requests are not audited to keep volume sane;
fine-grained domain events are logged explicitly by services.
"""

import contextlib
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionFactory
from app.models.audit import AuditLog

log = get_logger(__name__)

_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)

        if request.method not in _AUDITED_METHODS:
            return response
        if not request.url.path.startswith(settings.api_v1_prefix):
            return response

        principal = getattr(request.state, "principal", None)
        actor_id = None
        if principal is not None:
            with contextlib.suppress(ValueError, TypeError):
                actor_id = uuid.UUID(principal.user_id)

        resource_type = _resource_from_path(request.url.path)
        record = AuditLog(
            actor_id=actor_id,
            action=f"{request.method.lower()}.{resource_type}",
            resource_type=resource_type,
            method=request.method,
            path=request.url.path[:512],
            status_code=response.status_code,
            ip_address=request.client.host if request.client else None,
            request_id=getattr(request.state, "request_id", None),
        )
        # Never let auditing break the request path.
        try:
            async with SessionFactory() as session:
                session.add(record)
                await session.commit()
        except Exception:  # pragma: no cover - defensive
            log.error("audit_write_failed", path=request.url.path, exc_info=True)
        return response


def _resource_from_path(path: str) -> str:
    parts = [p for p in path.removeprefix(settings.api_v1_prefix).split("/") if p]
    return parts[0] if parts else "root"
