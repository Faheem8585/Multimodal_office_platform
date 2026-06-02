"""Text embedding service.

Primary backend is sentence-transformers (all-MiniLM-L6-v2, 384-dim). The model
is loaded lazily and cached process-wide because loading is expensive — this
matters in Celery workers that handle many ingestion jobs.

A deterministic hashing fallback is used when sentence-transformers/torch are
unavailable (e.g. lightweight CI or local dev). It produces stable vectors of
the right dimension so the full ingestion + search path is exercisable without
a heavy ML stack. It is NOT semantically meaningful — never use it in prod.
"""

import hashlib
from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class Embedder(Protocol):
    dim: int

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, dim: int) -> None:
        from sentence_transformers import SentenceTransformer

        self.dim = dim
        self._model = SentenceTransformer(model_name)
        log.info("embedding_model_loaded", model=model_name, dim=dim)

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [v.tolist() for v in vectors]


class HashingEmbedder:
    """Deterministic, dependency-free fallback (NOT semantic)."""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in text.lower().split():
                h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    try:
        return SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dim)
    except Exception as exc:  # pragma: no cover - depends on env
        log.warning("embedder_fallback_to_hashing", error=str(exc))
        return HashingEmbedder(settings.embedding_dim)
