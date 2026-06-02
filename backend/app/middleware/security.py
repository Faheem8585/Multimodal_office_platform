"""Security headers middleware (defense-in-depth for OWASP Top 10).

These headers harden the browser-facing surface: clickjacking, MIME sniffing,
referrer leakage, and a restrictive CSP for the API (the SPA ships its own).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Environment, settings

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",  # modern browsers: rely on CSP, disable legacy auditor
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # API returns JSON only; lock the document context down hard.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for key, value in _HEADERS.items():
            response.headers.setdefault(key, value)
        # HSTS only in non-dev where TLS is terminated in front of us.
        if settings.environment != Environment.DEV:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response
