from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator

from faster_whisper import WhisperModel

from core.types import TranscriptionChunk


class WhisperSTTProvider:
    """STT adapter using faster-whisper for local inference."""

    def __init__(self, *, model_size: str = "base", device: str = "cpu") -> None:
        self._model = WhisperModel(model_size, device=device, compute_type="int8")

    def _transcribe_sync(self, audio: bytes, language: str | None) -> str:
        segments, _ = self._model.transcribe(io.BytesIO(audio), language=language)
        return " ".join(seg.text.strip() for seg in segments).strip()

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        return await asyncio.to_thread(self._transcribe_sync, audio, language)

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str | None = None,
    ) -> AsyncIterator[TranscriptionChunk]:
        chunks: list[bytes] = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        text = await self.transcribe(b"".join(chunks), language)
        yield TranscriptionChunk(text=text, is_final=True)
