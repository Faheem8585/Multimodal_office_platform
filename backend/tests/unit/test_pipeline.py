from datetime import date

import pytest

from app.modules.hr.service import business_days
from app.services.chunking import chunk_text
from app.services.embeddings import HashingEmbedder
from app.services.extraction import UnsupportedDocument, extract


def test_chunking_indices_and_overlap():
    text = "word " * 600  # one long paragraph forcing a hard split
    chunks = chunk_text(text, size=1000, overlap=150)
    assert len(chunks) >= 3
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(len(c.content) <= 1000 for c in chunks)


def test_chunking_empty():
    assert chunk_text("") == []


def test_chunking_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("hello", size=100, overlap=100)


def test_hashing_embedder_properties():
    emb = HashingEmbedder(384)
    v1, v2 = emb.encode(["leave policy", "leave policy"])
    assert len(v1) == 384
    assert v1 == v2  # deterministic
    assert abs(sum(x * x for x in v1) ** 0.5 - 1.0) < 1e-6  # normalized


def test_extract_text_and_unsupported():
    assert extract(b"Plain text", "text/plain", "n.txt").text == "Plain text"
    with pytest.raises(UnsupportedDocument):
        extract(b"...", "application/x-evil", "x.bin")


def test_business_days_counts_weekdays_inclusive():
    # Mon 2026-06-01 .. Fri 2026-06-05 => 5 working days.
    assert business_days(date(2026, 6, 1), date(2026, 6, 5)) == 5
    # Includes a weekend: Fri..next Mon => Fri, Mon = 2.
    assert business_days(date(2026, 6, 5), date(2026, 6, 8)) == 2
    with pytest.raises(ValueError):
        business_days(date(2026, 6, 5), date(2026, 6, 1))
