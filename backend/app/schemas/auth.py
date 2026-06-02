"""Auth and user schemas (Pydantic v2)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Department, RoleName


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    # Refresh token is returned in the body for non-browser clients; browser
    # clients receive it as an httpOnly cookie (see router).
    refresh_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = None  # falls back to cookie if omitted


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    department: Department
    is_active: bool
    roles: list[RoleName]
    last_login_at: datetime | None = None

    @classmethod
    def from_user(cls, user) -> "UserOut":  # type: ignore[no-untyped-def]
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            department=user.department,
            is_active=user.is_active,
            roles=sorted(user.role_names),
            last_login_at=user.last_login_at,
        )


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=256)
    department: Department
    roles: list[RoleName] = Field(default_factory=lambda: [RoleName.DEPT_MEMBER])


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=256)
