from __future__ import annotations

import numpy as np
from openwakeword.vad import VAD


class SpeechActivityDetector:
    """Thin wrapper around openwakeword's Silero VAD.

    Consumes raw 16kHz mono 16-bit PCM bytes and returns True when speech
    is detected above the configured threshold.
    """

    _FRAME_SIZE = 480  # 30ms at 16kHz

    def __init__(self, threshold: float = 0.5) -> None:
        self._vad = VAD()
        self._threshold = threshold

    def is_speech(self, frame: bytes) -> bool:
        """Return True if any VAD chunk in `frame` exceeds the threshold."""
        audio = np.frombuffer(frame, dtype=np.int16)
        scores = self._vad.predict(audio, frame_size=self._FRAME_SIZE)
        if isinstance(scores, (int, float, np.floating)):
            return float(scores) >= self._threshold
        return bool(np.any(np.array(scores) >= self._threshold))

    def reset(self) -> None:
        """Reset internal Silero state (call between activation cycles)."""
        self._vad = VAD()
