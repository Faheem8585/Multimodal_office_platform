"""Global semantic + full-text search across documents the caller may see."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentPrincipal, DbSession
from app.models.enums import Department
from app.repositories.document import DocumentRepository
from app.schemas.common import Page, PageParams
from app.schemas.document import DocumentOut
from app.schemas.search import SearchHit, SearchRequest, SearchResponse
from app.services.search import resolve_scope, semantic_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/semantic", response_model=SearchResponse)
async def semantic(
    body: SearchRequest, principal: CurrentPrincipal, db: DbSession
) -> SearchResponse:
    hits = await semantic_search(db, principal, body.query, body.department, body.limit)
    return SearchResponse(
        query=body.query,
        hits=[
            SearchHit(
                chunk_id=h.chunk_id,
                document_id=h.document_id,
                content=h.content,
                score=round(h.score, 4),
            )
            for h in hits
        ],
    )


@router.get("/fulltext", response_model=Page[DocumentOut])
async def fulltext(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    q: Annotated[str, Query(min_length=1, max_length=1000)],
    department: Annotated[Department | None, Query()] = None,
) -> Page[DocumentOut]:
    scope = resolve_scope(principal, department)
    if not scope:
        return Page(items=[], total=0, page=params.page, size=params.size)
    items, total = await DocumentRepository(db).fulltext_search(
        q, scope, params.offset, params.size
    )
    return Page(
        items=[DocumentOut.model_validate(d) for d in items],
        total=total,
        page=params.page,
        size=params.size,
    )
