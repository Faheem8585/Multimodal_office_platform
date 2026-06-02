"""Pluggable LLM provider interface for the RAG chat assistant.

The provider is swappable via the LLM_PROVIDER setting so the org can choose a
hosted model (Anthropic) or self-host later without touching call sites. An
`echo` provider is always available as a no-network fallback for dev/tests; it
returns an extractive answer from the retrieved context so the chat endpoint is
demonstrable and testable without API keys.
"""

import re
from typing import Protocol

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class LLMProvider(Protocol):
    async def complete(self, system: str, prompt: str) -> str: ...


class AnthropicProvider:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.llm_model

    async def complete(self, system: str, prompt: str) -> str:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


class OllamaProvider:
    """Free, self-hosted generation via a local Ollama server (no API cost).

    Set LLM_PROVIDER=ollama and run e.g. `ollama run llama3.2:3b`. Generates
    real, conversational answers grounded in the retrieved context, fully
    offline. Reachability is checked in get_llm_provider so a stopped server
    falls back to the echo provider instead of failing requests.
    """

    def __init__(self) -> None:
        self._base = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model

    async def complete(self, system: str, prompt: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self._base}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
            )
            r.raise_for_status()
            return r.json()["message"]["content"].strip()


class EchoProvider:
    """Network-free, no-cost fallback that gives an *extractive* answer.

    It can't generate text, but the RAG pipeline has already retrieved the
    relevant passages. Rather than dump whole chunks (which, for FAQ-style docs,
    contain many unrelated Q&As), we split the retrieved context into individual
    snippets and return only the one or two that best match the question's words.
    With a well-populated knowledge base this answers the specific question
    asked, for free — only the phrasing is verbatim rather than paraphrased.
    """

    _NO_MATCH = "I couldn't find anything relevant in this department's documents."
    # Common words that shouldn't drive relevance scoring.
    _STOP = frozenset(
        [
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "can",
            "do",
            "does",
            "for",
            "from",
            "get",
            "how",
            "i",
            "in",
            "is",
            "it",
            "its",
            "me",
            "my",
            "need",
            "of",
            "on",
            "or",
            "our",
            "the",
            "to",
            "up",
            "us",
            "we",
            "what",
            "when",
            "where",
            "which",
            "who",
            "why",
            "will",
            "with",
            "you",
            "your",
            "this",
            "that",
            "these",
            "those",
            "there",
            "here",
            "please",
            "tell",
            "about",
            "into",
        ]
    )

    def _tokens(self, text: str) -> list[str]:
        """Lowercase content tokens with light stemming, returned as a list so
        callers can weigh term frequency. Hyphens are stripped first ("Wi-Fi" ->
        "wifi"); trailing plurals are reduced ("printers" -> also "printer") so
        singular/plural queries still match."""
        out: list[str] = []
        for t in re.findall(r"[a-z0-9]+", text.lower().replace("-", "")):
            if t in self._STOP or len(t) <= 1:
                continue
            out.append(t)
            if t.endswith("ies") and len(t) > 4:
                out.append(t[:-3] + "y")
            elif t.endswith("es") and len(t) > 4:
                out.append(t[:-2])
            elif t.endswith("s") and len(t) > 3:
                out.append(t[:-1])
        return out

    async def complete(self, system: str, prompt: str) -> str:
        marker = "Context:\n"
        if marker not in prompt:
            return self._NO_MATCH

        body = prompt.split(marker, 1)[1]
        context, _, question = body.rpartition("\n\nQuestion: ")
        context = (context or body).strip()

        # Split into snippets: chunk separators ('---') then blank-line paragraphs.
        # Skip short title/section lines (no question mark, few words) so we never
        # answer with a document heading like "Remote access, VPN, and hardware."
        snippets: list[str] = []
        for chunk in context.split("\n\n---\n\n"):
            for para in re.split(r"\n\s*\n", chunk):
                p = " ".join(para.split()).strip()  # collapse wrapping newlines
                if len(p) <= 25:
                    continue
                is_heading = "?" not in p and len(p) < 90
                if not is_heading:
                    snippets.append(p)
        if not snippets:
            return self._NO_MATCH

        # Score by how many of the question's words appear (with frequency), so the
        # most on-point Q&A — not just any snippet mentioning the term — wins.
        q_words = set(self._tokens(question))
        scored = sorted(
            (
                (sum(1 for t in self._tokens(s) if t in q_words), -i, s)
                for i, s in enumerate(snippets)
            ),
            reverse=True,
        )
        best_score = scored[0][0]
        if best_score == 0:
            # No keyword overlap with any snippet — be honest, offer the closest.
            return (
                "I couldn't find a specific answer to that in this department's "
                f"documents. The closest related note is:\n\n{snippets[0][:500]}"
            )

        # Take the top snippet, plus a second only if it's clearly relevant too.
        chosen = [scored[0][2]]
        if len(scored) > 1 and scored[1][0] >= max(2, best_score - 1):
            chosen.append(scored[1][2])

        answer = "\n\n".join(self._as_answer(s) for s in chosen)
        return (
            f"{answer}\n\n"
            "(Answer drawn from your department's documents — enable an LLM "
            "provider for a fully conversational reply.)"
        )

    @staticmethod
    def _as_answer(snippet: str) -> str:
        """Turn an FAQ snippet ("How do I X? Do Y.") into a direct answer ("Do
        Y.") so it reads as a reply rather than echoing the question back."""
        if "?" in snippet:
            _question, _, body = snippet.partition("?")
            body = body.strip()
            if len(body) > 15:
                return body
        return snippet


def get_llm_provider() -> LLMProvider:
    """Resolve the configured provider, falling back to the always-available
    echo provider if the configured one is unavailable (missing key, server
    down) so the chat endpoint never hard-fails."""
    provider = settings.llm_provider
    if provider == "anthropic":
        try:
            return AnthropicProvider()
        except Exception as exc:  # pragma: no cover - depends on env
            log.warning("llm_provider_fallback_to_echo", error=str(exc))
    elif provider == "ollama":
        try:
            import httpx

            base = settings.ollama_base_url.rstrip("/")
            httpx.get(f"{base}/api/tags", timeout=2).raise_for_status()
            return OllamaProvider()
        except Exception as exc:  # pragma: no cover - depends on env
            log.warning("ollama_unreachable_fallback_to_echo", error=str(exc))
    return EchoProvider()
