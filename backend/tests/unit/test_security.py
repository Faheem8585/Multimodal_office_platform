import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("S3cret-Passw0rd!")
    assert h != "S3cret-Passw0rd!"  # not stored in plaintext
    assert verify_password("S3cret-Passw0rd!", h)
    assert not verify_password("wrong", h)


def test_verify_handles_garbage_hash():
    assert verify_password("anything", "not-a-valid-hash") is False


def test_access_token_roundtrip():
    token = create_access_token("user-1", {"dept": "hr", "roles": ["admin"]})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"
    assert payload["roles"] == ["admin"]


def test_expired_token_rejected():
    token = create_access_token("u", {"dept": "hr"}, ttl_seconds=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_tampered_token_rejected():
    token = create_access_token("u", {"dept": "hr"})
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token + "x")


def test_refresh_token_hash_is_deterministic_and_sized():
    raw = generate_refresh_token()
    assert hash_refresh_token(raw) == hash_refresh_token(raw)
    assert len(hash_refresh_token(raw)) == 64
    assert hash_refresh_token(raw) != hash_refresh_token(generate_refresh_token())
