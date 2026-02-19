from __future__ import annotations

import re


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

