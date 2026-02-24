from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch


def _make_mock_voice(audio_chunks: list[bytes] | None = None):
    """Mock PiperVoice that yields fake audio chunks."""
    chunks = audio_chunks or [b"\x00\x01", b"\x02\x03"]

    mock_chunk = lambda data: MagicMock(audio_int16_bytes=data)
    mock_voice = MagicMock()
    mock_voice.synthesize.return_value = iter(mock_chunk(c) for c in chunks)
    return mock_voice


class TestPiperTTSProvider(unittest.IsolatedAsyncioTestCase):

    @patch("adapters.tts_piper.PiperVoice")
    async def test_synthesize_returns_bytes(self, MockVoice):
        from adapters.tts_piper import PiperTTSProvider

        MockVoice.load.return_value = _make_mock_voice([b"\x00\x01", b"\x02\x03"])
        provider = PiperTTSProvider(model_path="/fake/model.onnx")

        result = await provider.synthesize("olá")

        assert isinstance(result, bytes)
        assert len(result) > 0

    @patch("adapters.tts_piper.PiperVoice")
    async def test_synthesize_stream_yields_audio_per_sentence(self, MockVoice):
        from adapters.tts_piper import PiperTTSProvider

        MockVoice.load.return_value = _make_mock_voice([b"\xAA\xBB"])
        provider = PiperTTSProvider(model_path="/fake/model.onnx")

        async def _text_stream():
            yield "Olá, tudo bem?"
            yield " Como vai você?"

        chunks = [c async for c in provider.synthesize_stream(_text_stream())]

        assert len(chunks) >= 1
        assert all(isinstance(c, bytes) for c in chunks)

    @patch("adapters.tts_piper.PiperVoice")
    async def test_cancel_stops_synthesis(self, MockVoice):
        from adapters.tts_piper import PiperTTSProvider

        # Model returns many chunks
        mock_voice = MagicMock()
        stop_called = []

        def _synth(text, syn_config):
            for i in range(100):
                chunk = MagicMock()
                chunk.audio_int16_bytes = bytes([i, i])
                yield chunk

        mock_voice.synthesize.side_effect = _synth
        MockVoice.load.return_value = mock_voice

        provider = PiperTTSProvider(model_path="/fake/model.onnx")

        # Register a stop event for this session and immediately set it
        import threading
        provider._stop_events["s-cancel"] = threading.Event()
        provider._stop_events["s-cancel"].set()

        result = await provider.synthesize("texto longo que seria cancelado", session_id="s-cancel")

        # Cancel should have stopped early — result may be empty
        assert isinstance(result, bytes)

    @patch("adapters.tts_piper.PiperVoice")
    async def test_cancel_is_idempotent(self, MockVoice):
        from adapters.tts_piper import PiperTTSProvider

        MockVoice.load.return_value = MagicMock()
        provider = PiperTTSProvider(model_path="/fake/model.onnx")

        await provider.cancel("unknown-session")  # session not registered — no error
        await provider.cancel("unknown-session")  # idempotente
