"""Department AI chat assistant grounded in that department's documents (RAG)."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.deps import CurrentPrincipal, DbSession
from app.core.ratelimit import limiter
from app.schemas.search import ChatRequest, ChatResponse, ChatSource
from app.services.rag import AccessDenied, answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("30/minute")  # LLM calls are expensive; cap per principal
async def chat(
    request: Request,
    response: Response,  # required by slowapi to inject rate-limit headers
    body: ChatRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> ChatResponse:
    try:
        result = await answer_question(db, principal, body.question, body.department, body.top_k)
    except AccessDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return ChatResponse(
        answer=result.answer,
        sources=[
            ChatSource(document_id=s.document_id, content=s.content, score=round(s.score, 4))
            for s in result.sources
        ],
    )
