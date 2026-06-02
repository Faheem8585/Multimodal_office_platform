"""User, Role and RefreshToken data access."""

import uuid
from datetime import datetime

from sqlalchemy import select, update

from app.models.enums import Department, RoleName
from app.models.user import RefreshToken, Role, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = self._base_select().where(User.email == email.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_roles(self, names: list[RoleName]) -> list[Role]:
        stmt = select(Role).where(Role.name.in_(names))
        return list((await self.session.execute(stmt)).scalars().all())

    async def users_with_role(self, department: Department, role: RoleName) -> list[User]:
        """Active users in a department holding (at least) a given role.

        Used to notify eligible approvers. Admins are always included since
        they can act on any department's approvals."""
        stmt = (
            self._base_select()
            .join(User.roles)
            .where(
                User.is_active.is_(True),
                Role.name.in_([role, RoleName.ADMIN]),
                (User.department == department) | (Role.name == RoleName.ADMIN),
            )
            .distinct()
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def touch_last_login(self, user_id: uuid.UUID, when: datetime) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_login_at=when)
        )


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        """Reuse detection: kill every token in a rotation lineage at once."""
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.family_id == family_id).values(revoked=True)
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
