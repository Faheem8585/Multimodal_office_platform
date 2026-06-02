"""Security primitives: password hashing (argon2) and JWT encode/decode.

- Passwords are hashed with Argon2id (memory-hard, current OWASP recommendation).
- Access tokens are short-lived JWTs carrying identity + RBAC claims.
- Refresh tokens are opaque random strings; only their hash is stored server-side
  so a DB leak does not expose usable tokens. Rotation logic lives in the auth
  service (see services/auth.py).
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_ph = PasswordHasher()


# --- Passwords ---
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


# --- Access tokens (JWT) ---
def create_access_token(
    subject: str, claims: dict[str, Any], ttl_seconds: int | None = None
) -> str:
    now = datetime.now(UTC)
    ttl = ttl_seconds or settings.access_token_ttl_seconds
    payload = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
        "jti": str(uuid.uuid4()),
        **claims,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.PyJWTError on any problem."""
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


# --- Refresh tokens (opaque) ---
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    # SHA-256 is fine here: the token is high-entropy random, not a low-entropy
    # password, so a fast hash for O(1) lookup is appropriate.
    return hashlib.sha256(token.encode()).hexdigest()
