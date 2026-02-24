from __future__ import annotations

import numpy as np
import unittest


class TestSpeechActivityDetector(unittest.TestCase):

    def test_silence_returns_false(self):
        from adapters.wakeword_vad import SpeechActivityDetector

        det = SpeechActivityDetector(threshold=0.5)
        silence = (np.zeros(480, dtype=np.int16)).tobytes()
        assert det.is_speech(silence) is False

    def test_reset_replaces_vad_instance(self):
        from adapters.wakeword_vad import SpeechActivityDetector

        det = SpeechActivityDetector(threshold=0.5)
        vad_before = det._vad
        det.reset()
        assert det._vad is not vad_before

    def test_accepts_multi_frame_input(self):
        """Passing 50 frames (24000 samples) should work without error."""
        from adapters.wakeword_vad import SpeechActivityDetector

        det = SpeechActivityDetector(threshold=0.5)
        audio = (np.zeros(24000, dtype=np.int16)).tobytes()
        result = det.is_speech(audio)
        assert isinstance(result, bool)

    def test_threshold_boundary_is_inclusive(self):
        """A score equal to threshold should return True (>= semantics)."""
        from unittest.mock import patch
        from adapters.wakeword_vad import SpeechActivityDetector
        import numpy as np

        det = SpeechActivityDetector(threshold=0.5)
        # Patch VAD.predict to return exactly the threshold value
        with patch.object(det._vad, "predict", return_value=np.float32(0.5)):
            result = det.is_speech(np.zeros(480, dtype=np.int16).tobytes())
        assert result is True
