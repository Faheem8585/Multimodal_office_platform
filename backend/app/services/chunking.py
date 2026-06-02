"""Text chunking for embedding/RAG.

Paragraph-aware, fixed-size chunks with overlap. Overlap preserves context
across boundaries so a sentence split between chunks is still retrievable.
Sizes are in characters (cheap, model-agnostic); good enough for MiniLM's
256-token window without a tokenizer dependency in the hot path.
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    index: int
    content: str


def chunk_text(text: str, *, size: int = 1000, overlap: int = 150) -> list[Chunk]:
    text = text.strip()
    if not text:
        return []
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    # Split on blank lines first, then pack paragraphs into ~size windows.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 2 <= size:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            if buf:
                chunks.append(buf)
            # Paragraph itself larger than a window: hard-split with overlap.
            if len(para) > size:
                chunks.extend(_hard_split(para, size, overlap))
                buf = ""
            else:
                buf = para
    if buf:
        chunks.append(buf)

    return [Chunk(index=i, content=c) for i, c in enumerate(chunks)]


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    step = size - overlap
    return [text[i : i + size] for i in range(0, len(text), step) if text[i : i + size]]
