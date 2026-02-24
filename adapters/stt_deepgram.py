from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from deepgram import DeepgramClient

from core.types import TranscriptionChunk


@dataclass
class PrerecordedOptions:
    """Options for the Deepgram prerecorded transcription API."""

    model: str = "nova-2"
    language: str = "pt-BR"
    smart_format: bool = True


class DeepgramSTTProvider:
    """STT adapter using Deepgram prerecorded API."""

    def __init__(self, *, api_key: str, language: str = "pt-BR") -> None:
        self._client = DeepgramClient(api_key)
        self._language = language

    def _transcribe_sync(self, audio: bytes, language: str | None) -> str:
        lang = language or self._language
        options = PrerecordedOptions(model="nova-2", language=lang, smart_format=True)
        source = {"buffer": audio}
        response = self._client.listen.prerecorded.v("1").transcribe_file(source, options)
        return response.results.channels[0].alternatives[0].transcript

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
