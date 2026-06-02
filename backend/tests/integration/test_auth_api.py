"""Integration tests for the auth flow against a real DB.

Skipped automatically when no test database is reachable (see conftest).
"""

import pytest

from tests.conftest import SEED, TEST_PASSWORD

pytestmark = pytest.mark.integration


async def test_login_and_me(client, seeded):
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": SEED["admin"], "password": TEST_PASSWORD},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == SEED["admin"]
    assert "admin" in me.json()["roles"]


async def test_login_rejects_bad_password(client, seeded):
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": SEED["admin"], "password": "wrong-password"},
    )
    assert res.status_code == 401


async def test_refresh_rotation_and_reuse_detection(client, seeded):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": SEED["hr_manager"], "password": TEST_PASSWORD},
    )
    refresh1 = login.json()["refresh_token"]

    # First rotation succeeds and returns a new refresh token.
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
    assert r2.status_code == 200, r2.text
    refresh2 = r2.json()["refresh_token"]
    assert refresh2 != refresh1

    # Replaying the old (now revoked) token is detected and rejected.
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
    assert reuse.status_code == 401

    # And reuse detection revoked the whole family, so refresh2 is dead too.
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh2})
    assert after.status_code == 401


async def test_protected_endpoint_requires_auth(client):
    res = await client.get("/api/v1/dashboard")
    assert res.status_code == 401
