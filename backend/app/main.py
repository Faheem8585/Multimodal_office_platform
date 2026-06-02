"""Application factory: wires config, middleware, observability and routers.

Kept as a factory (`create_app`) so tests can build isolated app instances.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.ratelimit import limiter
from app.core.telemetry import init_sentry, instrument_app
from app.middleware.audit import AuditMiddleware
from app.middleware.context import RequestContextMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.routers import api_router, health

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    log.info("app_startup", environment=settings.environment)
    yield
    from app.db.session import engine

    await engine.dispose()
    log.info("app_shutdown")


def create_app() -> FastAPI:
    configure_logging()
    init_sentry()

    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Rate limiting (slowapi needs the limiter on app.state).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]

    # Middleware: added inner-first; RequestContext is added last => outermost,
    # so request_id is bound before anything else runs.
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    # Observability (metrics + optional tracing).
    instrument_app(app)

    # Generic error envelope (don't leak internals in prod).
    app.add_exception_handler(Exception, _unhandled_handler)

    # Routes.
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "code": "rate_limited",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    log.error("unhandled_exception", error=str(exc), exc_info=True)
    detail = "Internal server error"
    if settings.debug:
        detail = f"{type(exc).__name__}: {exc}"
    return JSONResponse(
        status_code=500,
        content={"detail": detail, "code": "internal_error", "request_id": request_id},
    )


app = create_app()
