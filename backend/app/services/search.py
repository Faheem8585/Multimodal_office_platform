"""Search service: department-scoped semantic + full-text search.

Scope is derived from the principal, never from client input alone: a caller
can narrow to one department they may see, but can never widen beyond their RBAC
scope. Admins see all departments.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department
from app.repositories.document import DocumentRepository, ScoredChunk
from app.services.embeddings import get_embedder
from app.services.rbac import Principal


def allowed_departments(principal: Principal) -> list[Department]:
    if principal.is_admin:
        return list(Department)
    return [principal.department]


def resolve_scope(principal: Principal, requested: Department | None) -> list[Department]:
    """Intersect the requested department (if any) with what the caller may see."""
    allowed = allowed_departments(principal)
    if requested is None:
        return allowed
    return [requested] if requested in allowed else []


async def semantic_search(
    session: AsyncSession,
    principal: Principal,
    query: str,
    requested_department: Department | None,
    limit: int,
) -> list[ScoredChunk]:
    scope = resolve_scope(principal, requested_department)
    if not scope:
        return []
    embedder = get_embedder()
    query_vec = embedder.encode([query])[0]
    return await DocumentRepository(session).semantic_search(query_vec, scope, limit)
