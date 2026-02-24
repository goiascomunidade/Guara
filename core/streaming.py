from __future__ import annotations

import re
from collections.abc import AsyncIterator


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_text_for_streaming(text: str, *, max_chunk_chars: int = 120) -> list[str]:
    """Split text into natural chunks for optimistic TTS playback."""
    normalized = " ".join(text.split())
    if not normalized:
        return []

    sentences = SENTENCE_SPLIT_RE.split(normalized)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if not current:
            current = sentence
            continue

        candidate = f"{current} {sentence}"
        if len(candidate) <= max_chunk_chars:
            current = candidate
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


SENTENCE_END_CHARS = frozenset(".!?")


async def sentence_buffer(
    token_stream: AsyncIterator[str],
    *,
    min_chars: int = 1,
) -> AsyncIterator[str]:
    """Accumulate LLM tokens and yield complete sentences for TTS.

    Yields a sentence whenever a sentence-ending character (.!?) is
    encountered and the buffer has at least min_chars characters.
    Any remaining buffer is yielded at stream end.
    """
    buffer = ""
    async for token in token_stream:
        buffer += token
        if any(buffer.rstrip().endswith(c) for c in SENTENCE_END_CHARS):
            sentence = buffer.strip()
            if len(sentence) >= min_chars:
                yield sentence
                buffer = ""

    remainder = buffer.strip()
    if remainder:
        yield remainder

