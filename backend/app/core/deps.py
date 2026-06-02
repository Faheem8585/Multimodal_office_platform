"""FastAPI dependencies: DB session, current principal, RBAC guards.

The current principal is rebuilt from the signed JWT claims — no DB round-trip
on every request. Endpoints that need the live User row use `get_current_user`.
"""

import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import Department, RoleName
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.rbac import Principal

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_principal(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(creds.credentials)
        principal = Principal.from_claims(payload["sub"], payload)
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    # Stash for the audit middleware.
    request.state.principal = principal
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def get_current_user(principal: CurrentPrincipal, db: DbSession) -> User:
    user = await UserRepository(db).get(uuid.UUID(principal.user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(minimum: RoleName) -> Callable:
    """Dependency factory: caller must hold at least `minimum` tier."""

    async def _guard(principal: CurrentPrincipal) -> Principal:
        if not principal.has_at_least(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role >= {minimum.value}",
            )
        return principal

    return _guard


def require_admin() -> Callable:
    return require_role(RoleName.ADMIN)


def require_department_access(get_dept: Callable) -> Callable:
    """Guard a route whose target department is derived from the request.

    `get_dept` is a callable dependency returning the Department in question.
    """

    async def _guard(
        principal: CurrentPrincipal,
        dept: Annotated[Department, Depends(get_dept)],
    ) -> Principal:
        if not principal.can_access_department(dept):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Outside your department scope",
            )
        return principal

    return _guard
