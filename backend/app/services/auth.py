"""Authentication service: login, refresh-token rotation, logout.

Refresh-token rotation with reuse detection (OWASP-recommended):
  - Each successful refresh REVOKES the presented token and issues a new one in
    the same `family_id`.
  - If a token that is already revoked is presented again, that is a signal the
    token was stolen and replayed, so the ENTIRE family is revoked, forcing
    re-authentication. This bounds the blast radius of a leaked refresh token.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.repositories.user import RefreshTokenRepository, UserRepository
from app.services.rbac import Principal

log = get_logger(__name__)


class AuthError(Exception):
    """Authentication failed (bad credentials, expired/replayed token)."""


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)

    # --- Login ---
    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email.lower())
        # Always run a hash verify to keep timing constant whether or not the
        # user exists, mitigating user-enumeration via response timing.
        candidate_hash = user.hashed_password if user else _DUMMY_HASH
        ok = verify_password(password, candidate_hash)
        if not user or not ok or not user.is_active:
            raise AuthError("invalid credentials")

        # Opportunistically upgrade the hash if argon2 params changed.
        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)

        await self.users.touch_last_login(user.id, datetime.now(UTC))
        return user

    # --- Token issuance ---
    def _principal_for(self, user: User) -> Principal:
        return Principal(
            user_id=str(user.id),
            email=user.email,
            department=user.department,
            roles=frozenset(user.role_names),
        )

    async def issue_tokens(
        self,
        user: User,
        *,
        family_id: uuid.UUID | None = None,
        user_agent: str = "",
        ip_address: str = "",
    ) -> tuple[str, str]:
        principal = self._principal_for(user)
        access = create_access_token(str(user.id), principal.to_claims())

        raw_refresh = generate_refresh_token()
        record = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            family_id=family_id or uuid.uuid4(),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.refresh_token_ttl_seconds),
            user_agent=user_agent[:255],
            ip_address=ip_address[:64],
        )
        self.tokens.add(record)
        await self.session.flush()
        return access, raw_refresh

    # --- Refresh with rotation + reuse detection ---
    async def refresh(
        self, raw_refresh: str, *, user_agent: str = "", ip_address: str = ""
    ) -> tuple[str, str]:
        record = await self.tokens.get_by_hash(hash_refresh_token(raw_refresh))
        if record is None:
            raise AuthError("unknown refresh token")

        if record.revoked:
            # Replay of an already-rotated token => compromise. Burn the family.
            log.warning(
                "refresh_token_reuse_detected",
                user_id=str(record.user_id),
                family_id=str(record.family_id),
            )
            await self.tokens.revoke_family(record.family_id)
            raise AuthError("refresh token reuse detected")

        if record.expires_at < datetime.now(UTC):
            raise AuthError("refresh token expired")

        user = await self.users.get(record.user_id)
        if user is None or not user.is_active:
            raise AuthError("user inactive")

        # Rotate: revoke current, mint a successor in the same family.
        record.revoked = True
        return await self.issue_tokens(
            user,
            family_id=record.family_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    async def logout(self, raw_refresh: str) -> None:
        record = await self.tokens.get_by_hash(hash_refresh_token(raw_refresh))
        if record and not record.revoked:
            await self.tokens.revoke_family(record.family_id)

    async def logout_all(self, user_id: uuid.UUID) -> None:
        await self.tokens.revoke_all_for_user(user_id)


# Pre-computed argon2 hash of a random string, used for constant-time rejects.
_DUMMY_HASH = hash_password("dummy-password-for-constant-time-compare")
