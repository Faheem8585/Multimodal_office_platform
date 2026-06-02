"""Authentication endpoints: login, refresh, logout, current user, register."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import Environment, settings
from app.core.deps import DbSession, get_current_user, require_admin
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserOut,
)
from app.services.auth import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)

_REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.environment != Environment.DEV,
        samesite="strict",  # primary CSRF defense for the cookie flow
        max_age=settings.refresh_token_ttl_seconds,
        path=settings.api_v1_prefix + "/auth",
    )


def _client_meta(request: Request) -> tuple[str, str]:
    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    return ua, ip


@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest, request: Request, response: Response, db: DbSession
) -> TokenPair:
    svc = AuthService(db)
    try:
        user = await svc.authenticate(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        ) from exc

    ua, ip = _client_meta(request)
    access, refresh = await svc.issue_tokens(user, user_agent=ua, ip_address=ip)
    _set_refresh_cookie(response, refresh)
    log.info("login_success", user_id=str(user.id))
    return TokenPair(
        access_token=access,
        expires_in=settings.access_token_ttl_seconds,
        refresh_token=refresh,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest, request: Request, response: Response, db: DbSession
) -> TokenPair:
    raw = body.refresh_token or request.cookies.get(_REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    svc = AuthService(db)
    ua, ip = _client_meta(request)
    try:
        access, new_refresh = await svc.refresh(raw, user_agent=ua, ip_address=ip)
    except AuthError as exc:
        # Clear the (now-invalid) cookie so the client stops replaying it.
        response.delete_cookie(_REFRESH_COOKIE, path=settings.api_v1_prefix + "/auth")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    _set_refresh_cookie(response, new_refresh)
    return TokenPair(
        access_token=access,
        expires_in=settings.access_token_ttl_seconds,
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest, request: Request, response: Response, db: DbSession
) -> Response:
    raw = body.refresh_token or request.cookies.get(_REFRESH_COOKIE)
    if raw:
        await AuthService(db).logout(raw)
    response.delete_cookie(_REFRESH_COOKIE, path=settings.api_v1_prefix + "/auth")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.from_user(user)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin())],
)
async def create_user(body: UserCreate, db: DbSession) -> UserOut:
    """Admin-only user provisioning."""
    from app.core.security import hash_password

    svc = AuthService(db)
    if await svc.users.get_by_email(body.email.lower()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    roles = await svc.users.get_roles(body.roles)
    user = User(
        email=body.email.lower(),
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        department=body.department,
        roles=roles,
    )
    svc.users.add(user)
    await db.flush()
    log.info("user_created", user_id=str(user.id), by_admin=True)
    return UserOut.from_user(user)
