"""Role-based access control: principals and department-scoped permissions.

Authorization is two-dimensional:
  1. Role tier (admin > dept_manager > dept_member > viewer) — what you can do.
  2. Department scope — whose data you can touch.

Admins are org-wide. Everyone else is confined to their own department unless a
resource is explicitly cross-department (e.g. an IT ticket raised by another
department is still managed by IT). Helpers here are pure; the FastAPI wiring
that turns a failed check into a 403 lives in core/deps.py.
"""

from dataclasses import dataclass

from app.models.enums import Department, RoleName

# Ordered tiers for "at least this role" checks.
_ROLE_RANK: dict[RoleName, int] = {
    RoleName.VIEWER: 0,
    RoleName.DEPT_MEMBER: 1,
    RoleName.DEPT_MANAGER: 2,
    RoleName.ADMIN: 3,
}


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, reconstructed from JWT claims (no DB hit)."""

    user_id: str
    email: str
    department: Department
    roles: frozenset[RoleName]

    @property
    def is_admin(self) -> bool:
        return RoleName.ADMIN in self.roles

    @property
    def max_rank(self) -> int:
        return max((_ROLE_RANK[r] for r in self.roles), default=-1)

    def has_at_least(self, role: RoleName) -> bool:
        return self.max_rank >= _ROLE_RANK[role]

    def can_access_department(self, dept: Department) -> bool:
        """Read/operate within a department's data."""
        return self.is_admin or self.department == dept

    def can_manage_department(self, dept: Department) -> bool:
        """Manager-level actions (approvals, config) within a department."""
        if self.is_admin:
            return True
        return self.department == dept and self.has_at_least(RoleName.DEPT_MANAGER)

    def to_claims(self) -> dict:
        return {
            "email": self.email,
            "dept": self.department.value,
            "roles": sorted(r.value for r in self.roles),
        }

    @classmethod
    def from_claims(cls, sub: str, claims: dict) -> "Principal":
        return cls(
            user_id=sub,
            email=claims.get("email", ""),
            department=Department(claims["dept"]),
            roles=frozenset(RoleName(r) for r in claims.get("roles", [])),
        )


class PermissionError(Exception):
    """Raised by pure permission checks; mapped to HTTP 403 by deps."""
