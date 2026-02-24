from __future__ import annotations

import numpy as np
import unittest


class TestSpeechActivityDetector(unittest.TestCase):

    def test_silence_returns_false(self):
        from adapters.wakeword_vad import SpeechActivityDetector

        det = SpeechActivityDetector(threshold=0.5)
        silence = (np.zeros(480, dtype=np.int16)).tobytes()
        assert det.is_speech(silence) is False

    def test_reset_clears_state(self):
        from adapters.wakeword_vad import SpeechActivityDetector

        det = SpeechActivityDetector(threshold=0.5)
        det.reset()  # should not raise

    def test_accepts_multi_frame_input(self):
        """Passing 50 frames (24000 samples) should work without error."""
        from adapters.wakeword_vad import SpeechActivityDetector

        det = SpeechActivityDetector(threshold=0.5)
        audio = (np.zeros(24000, dtype=np.int16)).tobytes()
        result = det.is_speech(audio)
        assert isinstance(result, bool)
