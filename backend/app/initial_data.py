"""Idempotent database seeding.

Creates the RBAC roles, an initial admin, one user per reference department, and
sensible default approval workflows so the platform is usable immediately after
`alembic upgrade head`. Safe to re-run: every step checks for existing rows.

Run with:  python -m app.initial_data
Admin credentials come from SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD env vars
(falling back to dev defaults — change these before any real deployment).
"""

import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import SessionFactory
from app.models.approval import ApprovalWorkflow, ApprovalWorkflowStep
from app.models.enums import Department, RoleName
from app.models.user import Role, User

log = get_logger(__name__)


async def _ensure_roles(session: AsyncSession) -> dict[RoleName, Role]:
    existing = {r.name: r for r in (await session.execute(select(Role))).scalars().all()}
    descriptions = {
        RoleName.ADMIN: "Organisation-wide administrator",
        RoleName.DEPT_MANAGER: "Department manager",
        RoleName.DEPT_MEMBER: "Department member",
        RoleName.VIEWER: "Read-only access",
    }
    for name, desc in descriptions.items():
        if name not in existing:
            role = Role(name=name, description=desc)
            session.add(role)
            existing[name] = role
    await session.flush()
    return existing


async def _ensure_user(
    session: AsyncSession,
    roles: dict[RoleName, Role],
    *,
    email: str,
    name: str,
    password: str,
    department: Department,
    role_names: list[RoleName],
) -> User:
    found = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if found:
        return found
    user = User(
        email=email,
        full_name=name,
        hashed_password=hash_password(password),
        department=department,
        roles=[roles[r] for r in role_names],
    )
    session.add(user)
    await session.flush()
    log.info("seeded_user", email=email)
    return user


async def _ensure_workflow(
    session: AsyncSession,
    *,
    name: str,
    department: Department,
    resource_type: str,
    trigger: dict,
    steps: list[dict],
) -> None:
    exists = (
        await session.execute(
            select(ApprovalWorkflow).where(
                ApprovalWorkflow.department == department,
                ApprovalWorkflow.resource_type == resource_type,
            )
        )
    ).scalar_one_or_none()
    if exists:
        return
    workflow = ApprovalWorkflow(
        name=name,
        department=department,
        resource_type=resource_type,
        trigger=trigger,
        steps=[
            ApprovalWorkflowStep(
                order_index=i,
                name=s["name"],
                required_role=s["role"],
                required_department=s.get("department"),
            )
            for i, s in enumerate(steps)
        ],
    )
    session.add(workflow)
    log.info("seeded_workflow", resource_type=resource_type, department=department.value)


async def seed() -> None:
    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
    admin_password = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe!Admin123")

    async with SessionFactory() as session:
        roles = await _ensure_roles(session)

        await _ensure_user(
            session,
            roles,
            email=admin_email,
            name="Platform Admin",
            password=admin_password,
            department=Department.IT,
            role_names=[RoleName.ADMIN],
        )
        # One manager + member per reference department for demoing RBAC.
        for dept in (Department.HR, Department.FINANCE, Department.IT):
            await _ensure_user(
                session,
                roles,
                email=f"{dept.value}.manager@example.com",
                name=f"{dept.value.upper()} Manager",
                password="ChangeMe!Mgr123",
                department=dept,
                role_names=[RoleName.DEPT_MANAGER],
            )
            await _ensure_user(
                session,
                roles,
                email=f"{dept.value}.member@example.com",
                name=f"{dept.value.upper()} Member",
                password="ChangeMe!Mem123",
                department=dept,
                role_names=[RoleName.DEPT_MEMBER],
            )

        # Default approval workflows.
        # Leave is approved by the employee's own department manager, so seed a
        # leave workflow for every department that has staff.
        for dept in (Department.HR, Department.FINANCE, Department.IT):
            await _ensure_workflow(
                session,
                name=f"{dept.value.upper()} leave approval",
                department=dept,
                resource_type="leave_request",
                trigger={},  # all leave needs manager sign-off
                steps=[
                    {
                        "name": "Manager approval",
                        "role": RoleName.DEPT_MANAGER,
                        "department": dept,
                    }
                ],
            )
        await _ensure_workflow(
            session,
            name="Large expense approval",
            department=Department.FINANCE,
            resource_type="expense",
            trigger={">": [{"var": "amount"}, 1000]},  # only > 1000 needs approval
            steps=[
                {
                    "name": "Finance manager",
                    "role": RoleName.DEPT_MANAGER,
                    "department": Department.FINANCE,
                },
                {"name": "Admin sign-off", "role": RoleName.ADMIN},
            ],
        )
        await _ensure_workflow(
            session,
            name="Access request approval",
            department=Department.IT,
            resource_type="access_request",
            trigger={},
            steps=[{"name": "IT manager", "role": RoleName.DEPT_MANAGER}],
        )

        await session.commit()
    log.info("seed_complete")


def run() -> None:
    configure_logging()
    asyncio.run(seed())


if __name__ == "__main__":
    run()
