"""Redis-backed rate limiting (sliding window) via slowapi.

Keyed by authenticated user when available, else client IP, so one noisy tenant
can't exhaust another's budget. Backed by Redis so limits hold across replicas.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings


def _rate_key(request: Request) -> str:
    principal = getattr(request.state, "principal", None)
    if principal is not None:
        return f"user:{principal.user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_rate_key,
    storage_uri=str(settings.redis_url),
    default_limits=[settings.rate_limit_default],
    headers_enabled=True,
)
