"""End-to-end voice-to-voice integration tests using stub providers only.

All six scenarios exercise the full GuaraRuntime pipeline without touching any
real API.  The stub providers satisfy the structural Protocol contracts defined
in core/contracts.py via duck typing — no inheritance needed.
"""
from __future__ import annotations

import base64
import io
import struct
import unittest
import wave

from core.types import TranscriptionChunk
from runtime.app import GuaraRuntime


# ---------------------------------------------------------------------------
# Stub providers
# ---------------------------------------------------------------------------


class _StubSTT:
    def __init__(self, fixed_text: str) -> None:
        self._text = fixed_text

    async def transcribe(self, audio: bytes, language=None) -> str:
        return self._text

    async def transcribe_stream(self, audio_stream, language=None):
        async for _ in audio_stream:
            pass
        yield TranscriptionChunk(text=self._text, is_final=True)


class _StubLLM:
    def __init__(self, fixed_reply: str) -> None:
        self._reply = fixed_reply

    async def complete(self, messages, tools=None) -> dict:
        return {"content": self._reply, "tool_calls": []}

    async def stream(self, messages, tools=None):
        for char in self._reply:
            yield char


class _StubTTS:
    async def synthesize(self, text: str, voice=None) -> bytes:
        return text.encode("utf-8")

    async def synthesize_stream(self, text_stream, voice=None):
        async for token in text_stream:
            yield token.encode("utf-8")

    async def cancel(self, session_id: str) -> None:
        pass


# ---------------------------------------------------------------------------
# WAV helper
# ---------------------------------------------------------------------------


def _make_wav_bytes(*, duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    num_samples = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(struct.pack(f"<{num_samples}h", *([0] * num_samples)))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestE2EV2V(unittest.IsolatedAsyncioTestCase):
    """Six end-to-end scenarios covering the full V2V pipeline with stubs."""

    # ------------------------------------------------------------------
    # 1. Full audio turn — WAV in, transcript + reply + audio out
    # ------------------------------------------------------------------
    async def test_full_audio_turn_produces_response(self) -> None:
        """WAV bytes → STT stub → LLM stub → TTS stub → base64 audio."""
        stt = _StubSTT("olá guara")
        llm = _StubLLM("olá usuário")
        tts = _StubTTS()

        app = GuaraRuntime(stt_provider=stt, llm_provider=llm, tts_provider=tts)
        session = await app.start_session(user_id="user-audio-1")
        wav = _make_wav_bytes(duration_ms=200)

        result = await app.process_audio_turn(session["session_id"], wav)

        self.assertIn("transcript", result)
        self.assertEqual(result["transcript"], "olá guara")

        self.assertIn("reply_text", result)
        self.assertEqual(result["reply_text"], "olá usuário")

        self.assertIn("audio_base64", result)
        decoded = base64.b64decode(result["audio_base64"]).decode("utf-8")
        self.assertEqual(decoded, "olá usuário")

    # ------------------------------------------------------------------
    # 2. Text turn — text in, reply_text out
    # ------------------------------------------------------------------
    async def test_text_turn_returns_reply(self) -> None:
        """Plain text input goes through LLM stub and returns the expected reply."""
        llm = _StubLLM("resposta do assistente")
        tts = _StubTTS()

        app = GuaraRuntime(llm_provider=llm, tts_provider=tts)
        session = await app.start_session(user_id="user-text-1")

        result = await app.process_text_turn(session["session_id"], "boa tarde")

        self.assertIn("reply_text", result)
        self.assertEqual(result["reply_text"], "resposta do assistente")
        self.assertIn("audio_base64", result)

    # ------------------------------------------------------------------
    # 3. Barge-in — interrupt_session returns cancelled_calls list
    # ------------------------------------------------------------------
    async def test_barge_in_returns_cancelled_calls(self) -> None:
        """Calling interrupt_session on an idle session returns an empty
        cancelled_calls list (no in-flight tool calls), but the key must exist."""
        app = GuaraRuntime(
            llm_provider=_StubLLM("ok"),
            tts_provider=_StubTTS(),
        )
        session = await app.start_session(user_id="user-barge-1")

        # Run a simple turn first so the session is in a known state.
        await app.process_text_turn(session["session_id"], "olá")

        result = await app.interrupt_session(session["session_id"])

        self.assertIn("cancelled_calls", result)
        self.assertIsInstance(result["cancelled_calls"], list)

    # ------------------------------------------------------------------
    # 4. Events — turn events are recorded after a full turn
    # ------------------------------------------------------------------
    async def test_events_emitted_for_full_turn(self) -> None:
        """After running a turn the event store must contain at least one event
        whose name contains 'turn'."""
        app = GuaraRuntime(
            llm_provider=_StubLLM("evento ok"),
            tts_provider=_StubTTS(),
        )
        session = await app.start_session(user_id="user-events-1")
        sid = session["session_id"]

        await app.process_text_turn(sid, "teste de eventos")

        events_payload = await app.get_events(session_id=sid, limit=50)
        self.assertIn("events", events_payload)
        events = events_payload["events"]
        self.assertTrue(events, "Expected at least one event in the store")

        names = [e["event_name"] for e in events]
        turn_events = [n for n in names if "turn" in n]
        self.assertTrue(
            turn_events,
            f"Expected at least one 'turn' event; found: {names}",
        )

    # ------------------------------------------------------------------
    # 5. Provider switch mid-session — new LLM reply is used
    # ------------------------------------------------------------------
    async def test_provider_switch_mid_session(self) -> None:
        """Switch the active LLM provider after session start and verify the
        next turn uses the new provider's response."""
        llm_first = _StubLLM("primeira resposta")
        llm_second = _StubLLM("segunda resposta do novo provedor")
        tts = _StubTTS()

        app = GuaraRuntime(llm_provider=llm_first, tts_provider=tts)
        session = await app.start_session(user_id="user-switch-1")
        sid = session["session_id"]

        first_result = await app.process_text_turn(sid, "pergunta um")
        self.assertEqual(first_result["reply_text"], "primeira resposta")

        # Register and activate the new provider.
        await app.register_provider(
            kind="llm",
            name="stub-llm-v2",
            provider=llm_second,
            activate=True,
        )

        second_result = await app.process_text_turn(sid, "pergunta dois")
        self.assertEqual(second_result["reply_text"], "segunda resposta do novo provedor")

    # ------------------------------------------------------------------
    # 6. Multiple sessions are independent
    # ------------------------------------------------------------------
    async def test_multiple_sessions_are_independent(self) -> None:
        """Two sessions created on the same runtime must have different IDs
        and both must receive the stub LLM reply independently."""
        llm = _StubLLM("resposta compartilhada")
        tts = _StubTTS()

        app = GuaraRuntime(llm_provider=llm, tts_provider=tts)

        session_a = await app.start_session(user_id="user-a")
        session_b = await app.start_session(user_id="user-b")

        self.assertNotEqual(session_a["session_id"], session_b["session_id"])

        result_a = await app.process_text_turn(session_a["session_id"], "mensagem de a")
        result_b = await app.process_text_turn(session_b["session_id"], "mensagem de b")

        self.assertEqual(result_a["reply_text"], "resposta compartilhada")
        self.assertEqual(result_b["reply_text"], "resposta compartilhada")
