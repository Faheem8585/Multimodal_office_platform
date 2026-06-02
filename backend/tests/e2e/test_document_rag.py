"""End-to-end: upload -> ingest -> semantic search -> grounded chat.

Ingestion is invoked directly (not via Celery) so the test is deterministic and
needs no running worker. Embeddings use the deterministic hashing fallback when
sentence-transformers is absent, so the retrieval path is still exercised.
"""

import uuid

import pytest

pytestmark = pytest.mark.integration


async def test_document_lifecycle(client, db_session, seeded, as_user):
    from app.services.ingestion import ingest_document

    member = await as_user("finance_member")

    content = (
        b"Travel reimbursement policy: employees may claim up to 500 EUR per "
        b"trip for accommodation. Receipts are mandatory for all claims."
    )
    files = {"file": ("policy.txt", content, "text/plain")}
    data = {"department": "finance", "title": "Travel Policy"}
    upload = await client.post("/api/v1/documents", headers=member, files=files, data=data)
    assert upload.status_code == 202, upload.text
    doc_id = uuid.UUID(upload.json()["document"]["id"])

    # Process synchronously (the worker would normally do this).
    indexed = await ingest_document(db_session, doc_id)
    assert indexed >= 1

    # Semantic search finds the indexed content.
    search = await client.post(
        "/api/v1/search/semantic",
        headers=member,
        json={"query": "accommodation reimbursement limit", "department": "finance"},
    )
    assert search.status_code == 200
    assert len(search.json()["hits"]) >= 1

    # RAG chat returns an answer grounded in retrieved sources.
    chat = await client.post(
        "/api/v1/chat",
        headers=member,
        json={"question": "How much can I claim for accommodation?", "department": "finance"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["answer"]
    assert len(body["sources"]) >= 1


async def test_cross_department_search_is_scoped(client, db_session, seeded, as_user):
    """A finance member must not get HR-scoped hits."""
    member = await as_user("finance_member")
    res = await client.post(
        "/api/v1/search/semantic",
        headers=member,
        json={"query": "anything", "department": "hr"},
    )
    # Requesting a department outside scope yields no hits (not a 500).
    assert res.status_code == 200
    assert res.json()["hits"] == []
