"""Document endpoints: upload (multimodal ingest), list, download, delete, reindex.

Uploads are validated (size + content type), persisted to object storage, and
queued for background processing. The heavy extract/OCR/embed work never blocks
the request.
"""

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.core.deps import CurrentPrincipal, DbSession, require_role
from app.core.logging import get_logger
from app.models.document import Document
from app.models.enums import Department, DocumentStatus, RoleName
from app.repositories.document import DocumentRepository
from app.schemas.common import Page, PageParams
from app.schemas.document import DocumentOut, DocumentUploadResponse
from app.services.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])
log = get_logger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "text/plain",
    "text/markdown",
    "text/csv",
}


def _ensure_scope(principal, department: Department) -> None:  # type: ignore[no-untyped-def]
    if not principal.can_access_department(department):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Outside your department scope")


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role(RoleName.DEPT_MEMBER))],
)
async def upload_document(
    principal: CurrentPrincipal,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    department: Annotated[Department, Form()],
    title: Annotated[str | None, Form()] = None,
) -> DocumentUploadResponse:
    _ensure_scope(principal, department)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported content type: {file.content_type}",
        )

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit",
        )

    storage = get_storage()
    doc_id = uuid.uuid4()
    storage_key = f"{department.value}/{doc_id}/{file.filename}"
    storage.put(storage_key, data, file.content_type or "application/octet-stream")

    document = Document(
        id=doc_id,
        title=title or (file.filename or "untitled"),
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        storage_key=storage_key,
        department=department,
        status=DocumentStatus.UPLOADED,
        uploaded_by=uuid.UUID(principal.user_id),
    )
    DocumentRepository(db).add(document)
    await db.flush()

    task_id = _enqueue_ingest(doc_id)
    log.info("document_uploaded", document_id=str(doc_id), task_id=task_id)
    return DocumentUploadResponse(document=DocumentOut.model_validate(document), task_id=task_id)


@router.get("", response_model=Page[DocumentOut])
async def list_documents(
    principal: CurrentPrincipal,
    db: DbSession,
    params: Annotated[PageParams, Depends()],
    department: Annotated[Department | None, Query()] = None,
) -> Page[DocumentOut]:
    dept = department or principal.department
    _ensure_scope(principal, dept)
    items, total = await DocumentRepository(db).list_for_department(
        dept, params.offset, params.size
    )
    return Page(
        items=[DocumentOut.model_validate(d) for d in items],
        total=total,
        page=params.page,
        size=params.size,
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> Response:
    document = await DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    _ensure_scope(principal, document.department)
    data = get_storage().get(document.storage_key)
    return Response(
        content=data,
        media_type=document.content_type,
        headers={"Content-Disposition": f'attachment; filename="{document.filename}"'},
    )


@router.post("/{document_id}/reindex", response_model=DocumentUploadResponse)
async def reindex_document(
    document_id: uuid.UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    _: Annotated[object, Depends(require_role(RoleName.DEPT_MANAGER))],
) -> DocumentUploadResponse:
    document = await DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    _ensure_scope(principal, document.department)
    task_id = _enqueue_ingest(document_id)
    return DocumentUploadResponse(
        document=DocumentOut.model_validate(document),
        task_id=task_id,
        message="Reindex queued.",
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    _: Annotated[object, Depends(require_role(RoleName.DEPT_MANAGER))],
) -> Response:
    repo = DocumentRepository(db)
    document = await repo.get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    _ensure_scope(principal, document.department)
    await repo.soft_delete(document)  # soft delete preserves audit trail
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _enqueue_ingest(document_id: uuid.UUID) -> str | None:
    """Queue background ingestion. If the broker is unreachable, the document
    stays in `uploaded` and can be reindexed later — we never fail the upload."""
    try:
        from app.workers.tasks import ingest_document_task

        result = ingest_document_task.delay(str(document_id))
        return result.id
    except Exception as exc:  # pragma: no cover - broker-dependent
        log.error("enqueue_ingest_failed", document_id=str(document_id), error=str(exc))
        return None
