from __future__ import annotations

import unittest
from collections.abc import AsyncIterator

from core.contracts import ISTTProvider
from core.types import TranscriptionChunk


def test_transcription_chunk_defaults():
    chunk = TranscriptionChunk(text="olá", is_final=True)
    assert chunk.text == "olá"
    assert chunk.is_final is True
    assert chunk.confidence == 1.0


def test_transcription_chunk_partial():
    chunk = TranscriptionChunk(text="ol", is_final=False, confidence=0.7)
    assert chunk.is_final is False
    assert chunk.confidence == 0.7


async def _bytes_stream(data: bytes) -> AsyncIterator[bytes]:
    yield data


class _StubSTT:
    async def transcribe(self, audio: bytes, language=None) -> str:
        return audio.decode()

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language=None,
    ) -> AsyncIterator[TranscriptionChunk]:
        chunks = [chunk async for chunk in audio_stream]
        text = b"".join(chunks).decode()
        yield TranscriptionChunk(text=text, is_final=True)


class TestSTTStreamContract(unittest.IsolatedAsyncioTestCase):
    async def test_stt_stream_satisfies_protocol(self) -> None:
        provider: ISTTProvider = _StubSTT()
        stream = provider.transcribe_stream(_bytes_stream(b"oi"))
        results = [r async for r in stream]
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_final)
        self.assertEqual(results[0].text, "oi")
