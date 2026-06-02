"""Shared test fixtures.

Two tiers of tests:
  * unit       — pure logic, no I/O; always run.
  * integration— exercise the app + a real Postgres (pgvector) via httpx.
                 Skipped automatically when no test DB is reachable, so a bare
                 `pytest` still runs the unit suite locally; CI provides the DB.

Integration tests run each case inside a transaction that is rolled back, so
they are isolated and leave no residue. The app's get_db dependency is
overridden to hand out the test's transactional session.
"""

import asyncio
import os
import uuid

import pytest

os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests-1234567890")

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.enums import Department, RoleName  # noqa: E402
from app.services.rbac import Principal  # noqa: E402


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            import asyncpg

            url = str(settings.database_url).replace("postgresql+asyncpg", "postgresql")
            conn = await asyncio.wait_for(asyncpg.connect(url), timeout=2)
            await conn.close()
            return True
        except Exception:
            return False

    try:
        return asyncio.run(_check())
    except Exception:
        return False


DB_AVAILABLE = _db_reachable()


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    if DB_AVAILABLE:
        return
    skip = pytest.mark.skip(reason="no test database reachable (integration tests)")
    for item in items:
        if (
            "integration" in item.keywords
            or "tests/integration" in str(item.fspath)
            or "tests/e2e" in str(item.fspath)
        ):
            item.add_marker(skip)


# --- Integration fixtures (only meaningful when DB_AVAILABLE) ---
# Session-scoped async fixtures + tests share one event loop via the
# asyncio_default_*_loop_scope = "session" settings in pyproject.toml. Don't
# override the deprecated `event_loop` fixture here (pytest-asyncio 1.x).
@pytest.fixture(scope="session")
async def engine():  # type: ignore[no-untyped-def]
    from sqlalchemy.ext.asyncio import create_async_engine

    eng = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine):  # type: ignore[no-untyped-def]
    """A session bound to a transaction that is rolled back after the test."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def client(db_session):  # type: ignore[no-untyped-def]
    """httpx client against the ASGI app with get_db overridden to db_session.

    The override makes commit() a flush() so endpoint code that commits doesn't
    break the outer test transaction."""
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db
    from app.main import app

    async def _override_get_db():  # type: ignore[no-untyped-def]
        # Patch commit -> flush for the duration so the test transaction holds.
        original_commit = db_session.commit
        db_session.commit = db_session.flush  # type: ignore[method-assign]
        try:
            yield db_session
        finally:
            db_session.commit = original_commit  # type: ignore[method-assign]

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


TEST_PASSWORD = "Test1234!password"

# Emails for seeded users available to integration tests. Use a valid domain
# (EmailStr rejects reserved TLDs like .local/.test) and a `test.` prefix so
# they never collide with the app's own seed data.
SEED = {
    "admin": "test.admin@example.com",
    "hr_manager": "test.hr.manager@example.com",
    "finance_manager": "test.finance.manager@example.com",
    "finance_member": "test.finance.member@example.com",
    "it_manager": "test.it.manager@example.com",
}


@pytest.fixture(scope="session")
async def seeded(engine):  # type: ignore[no-untyped-def]
    """Commit roles + a fixed set of users so integration tests have real,
    FK-valid identities to authenticate as. Cleaned up at session end."""
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.security import hash_password
    from app.models.user import Role, User

    specs = [
        ("admin", Department.IT, [RoleName.ADMIN]),
        ("hr_manager", Department.HR, [RoleName.DEPT_MANAGER]),
        ("finance_manager", Department.FINANCE, [RoleName.DEPT_MANAGER]),
        ("finance_member", Department.FINANCE, [RoleName.DEPT_MEMBER]),
        ("it_manager", Department.IT, [RoleName.DEPT_MANAGER]),
    ]
    async with AsyncSession(engine, expire_on_commit=False) as s:
        roles = {r.name: r for r in (await s.execute(select(Role))).scalars().all()}
        for name in RoleName:
            if name not in roles:
                role = Role(name=name, description=name.value)
                s.add(role)
                roles[name] = role
        await s.flush()
        for key, dept, role_names in specs:
            existing = (
                await s.execute(select(User).where(User.email == SEED[key]))
            ).scalar_one_or_none()
            if existing is None:
                s.add(
                    User(
                        email=SEED[key],
                        full_name=key,
                        hashed_password=hash_password(TEST_PASSWORD),
                        department=dept,
                        roles=[roles[r] for r in role_names],
                    )
                )
        await s.commit()

    yield SEED

    async with AsyncSession(engine, expire_on_commit=False) as s:
        await s.execute(delete(User).where(User.email.in_(list(SEED.values()))))
        await s.commit()


@pytest.fixture
async def as_user(db_session):  # type: ignore[no-untyped-def]
    """Return a callable building auth headers for a seeded user by key."""
    from sqlalchemy import select

    from app.models.user import User

    async def _make(key: str) -> dict[str, str]:
        user = (await db_session.execute(select(User).where(User.email == SEED[key]))).scalar_one()
        principal = Principal(
            user_id=str(user.id),
            email=user.email,
            department=user.department,
            roles=frozenset(user.role_names),
        )
        return auth_header(principal)

    return _make


def make_principal(
    department: Department = Department.HR,
    roles: set[RoleName] | None = None,
    user_id: str | None = None,
) -> Principal:
    return Principal(
        user_id=user_id or str(uuid.uuid4()),
        email="t@example.com",
        department=department,
        roles=frozenset(roles or {RoleName.DEPT_MEMBER}),
    )


def auth_header(principal: Principal) -> dict[str, str]:
    token = create_access_token(principal.user_id, principal.to_claims())
    return {"Authorization": f"Bearer {token}"}
