from __future__ import annotations

from collections.abc import AsyncIterator

from core.types import TranscriptionChunk


class LocalSTTProvider:
    """Baseline STT provider for local development and tests."""

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        try:
            text = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""

        if text:
            return text

        language_hint = f" ({language})" if language else ""
        return f"<audio:{len(audio)} bytes{language_hint}>"

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str | None = None,
    ) -> AsyncIterator[TranscriptionChunk]:
        chunks: list[bytes] = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        audio = b"".join(chunks)
        text = await self.transcribe(audio, language)
        yield TranscriptionChunk(text=text, is_final=True)
