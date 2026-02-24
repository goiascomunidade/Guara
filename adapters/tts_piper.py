from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator

from piper import PiperVoice
from piper.config import SynthesisConfig


class PiperTTSProvider:
    """TTS adapter using Piper for local neural speech synthesis.

    Inspired by: /home/peras/gitperaro/nadir/agent_daemon/tts.py
    Output: int16 PCM bytes at 22050 Hz.
    """

    def __init__(self, *, model_path: str, length_scale: float = 1.0) -> None:
        self._voice = PiperVoice.load(model_path, use_cuda=False)
        self._syn_config = SynthesisConfig(length_scale=length_scale)
        self._stop_events: dict[str, threading.Event] = {}

    def _synthesize_sync(
        self,
        text: str,
        stop_event: threading.Event | None,
    ) -> bytes:
        chunks: list[bytes] = []
        for chunk in self._voice.synthesize(text, syn_config=self._syn_config):
            if stop_event is not None and stop_event.is_set():
                break
            chunks.append(chunk.audio_int16_bytes)
        return b"".join(chunks)

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        session_id: str | None = None,
    ) -> bytes:
        stop_event = self._stop_events.get(session_id) if session_id else None
        return await asyncio.to_thread(self._synthesize_sync, text, stop_event)

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Synthesize each sentence from the stream and yield audio chunks."""
        async for sentence in text_stream:
            if sentence.strip():
                audio = await self.synthesize(sentence, session_id=session_id)
                if audio:
                    yield audio

    async def cancel(self, session_id: str) -> None:
        """Signal active synthesis for this session to stop (barge-in support)."""
        if session_id in self._stop_events:
            self._stop_events[session_id].set()
