from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock


class TestWakeWordListener(unittest.TestCase):

    def _make_listener(self, *, wake_word="guará", stop_word="obrigado"):
        from runtime.listener import WakeWordListener

        runtime = MagicMock()
        runtime.start_session = AsyncMock(return_value={"session_id": "sess-1"})
        runtime.process_audio_turn = AsyncMock(
            return_value={
                "reply_text": "Olá!",
                "audio_base64": "",
                "transcript": "teste",
            }
        )
        return WakeWordListener(
            runtime=runtime,
            wake_word=wake_word,
            stop_word=stop_word,
            vad_threshold=0.5,
        )

    def test_init_stores_config(self):
        listener = self._make_listener(wake_word="guará", stop_word="obrigado")
        assert listener.wake_word == "guará"
        assert listener.stop_word == "obrigado"

    def test_pcm_to_wav_produces_valid_wav(self):
        import io
        import wave
        import numpy as np
        from runtime.listener import _pcm_to_wav

        frames = [np.zeros(480, dtype=np.int16).tobytes() for _ in range(10)]
        wav_bytes = _pcm_to_wav(frames)

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == 4800

    def test_wake_word_check_returns_true_when_word_in_transcript(self):
        listener = self._make_listener(wake_word="guará")
        result = listener._check_for_word("Guará, como você está?", "guará")
        assert result is True

    def test_wake_word_check_returns_false_when_absent(self):
        listener = self._make_listener(wake_word="guará")
        result = listener._check_for_word("Olá, tudo bem?", "guará")
        assert result is False

    def test_stop_word_check_case_insensitive(self):
        listener = self._make_listener(stop_word="obrigado")
        result = listener._check_for_word("Obrigado!", "obrigado")
        assert result is True
