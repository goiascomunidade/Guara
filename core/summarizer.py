from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class SummarizationConfig:
    max_context_tokens: int = 3_000
    max_unsummarized_messages: int = 16
    min_messages_to_keep: int = 4
    target_context_tokens: int = 600


@dataclass(frozen=True)
class SummaryResult:
    request_id: str
    summary: str
    last_summarized_index: int
    error: str | None = None


class ContextSummarizer:
    """Simple, deterministic summarizer trigger and response shape."""

    def __init__(self, config: SummarizationConfig | None = None) -> None:
        self._config = config or SummarizationConfig()

    def should_summarize(self, messages: list[dict[str, str]]) -> bool:
        if not messages:
            return False
        tokens = self.estimate_tokens(messages)
        return (
            tokens >= self._config.max_context_tokens
            or len(messages) >= self._config.max_unsummarized_messages
        )

    def estimate_tokens(self, messages: list[dict[str, str]]) -> int:
        # Fast approximation for routing decisions.
        text = " ".join(message.get("content", "") for message in messages)
        return max(1, int(len(text.split()) * 1.3))

    async def summarize(self, messages: list[dict[str, str]]) -> SummaryResult:
        request_id = str(uuid4())
        if not self.should_summarize(messages):
            return SummaryResult(
                request_id=request_id,
                summary="",
                last_summarized_index=-1,
                error="summarization not required",
            )

        if len(messages) <= self._config.min_messages_to_keep:
            return SummaryResult(
                request_id=request_id,
                summary="",
                last_summarized_index=-1,
                error="not enough messages to summarize",
            )

        cutoff = len(messages) - self._config.min_messages_to_keep - 1
        to_summarize = messages[: cutoff + 1]
        chunks = []
        for item in to_summarize:
            role = item.get("role", "unknown")
            content = item.get("content", "").strip()
            if not content:
                continue
            chunks.append(f"{role}: {content}")
        summary = " | ".join(chunks)

        if len(summary) > self._config.target_context_tokens:
            summary = summary[: self._config.target_context_tokens].rstrip() + "..."

        return SummaryResult(
            request_id=request_id,
            summary=summary,
            last_summarized_index=cutoff,
        )

