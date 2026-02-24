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


from core.contracts import ILLMProvider, ITTSProvider


class _StubTTS:
    def __init__(self):
        self.cancelled: list[str] = []

    async def synthesize(self, text: str, voice=None) -> bytes:
        return text.encode()

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice=None,
    ) -> AsyncIterator[bytes]:
        async for token in text_stream:
            yield token.encode()

    async def cancel(self, session_id: str) -> None:
        self.cancelled.append(session_id)


async def _str_stream(*tokens: str) -> AsyncIterator[str]:
    for t in tokens:
        yield t


class TestTTSStreamContract(unittest.IsolatedAsyncioTestCase):
    async def test_tts_stream_satisfies_protocol(self) -> None:
        provider: ITTSProvider = _StubTTS()
        chunks = [c async for c in provider.synthesize_stream(_str_stream("ol", "á"))]
        self.assertEqual(b"".join(chunks), "olá".encode())

    async def test_tts_cancel_is_idempotent(self) -> None:
        provider = _StubTTS()
        await provider.cancel("s-1")
        await provider.cancel("s-1")
        self.assertEqual(provider.cancelled, ["s-1", "s-1"])


class _StubLLM:
    async def complete(self, messages, tools=None) -> dict:
        return {"content": "ok", "tool_calls": []}

    async def stream(self, messages, tools=None) -> AsyncIterator[str]:
        for token in ["ol", "á"]:
            yield token


class TestLLMStreamContract(unittest.IsolatedAsyncioTestCase):
    async def test_llm_stream_satisfies_protocol(self) -> None:
        provider: ILLMProvider = _StubLLM()
        tokens = [t async for t in provider.stream([{"role": "user", "content": "oi"}])]
        self.assertEqual("".join(tokens), "olá")


class TestSTTStreamContract(unittest.IsolatedAsyncioTestCase):
    async def test_stt_stream_satisfies_protocol(self) -> None:
        provider: ISTTProvider = _StubSTT()
        stream = provider.transcribe_stream(_bytes_stream(b"oi"))
        results = [r async for r in stream]
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_final)
        self.assertEqual(results[0].text, "oi")
