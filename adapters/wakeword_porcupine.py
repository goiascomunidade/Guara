from __future__ import annotations

import logging
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PorcupineConfig:
    access_key: str
    keyword_path: str
    model_path: str = ""
    sensitivity: float = 0.5
    audio_device_index: int = -1


class PorcupineWakeWordDetector:
    """Dedicated wake word detector using Picovoice Porcupine + PvRecorder.

    Use as a context manager; call wait_for_wake_word() to block until the
    configured keyword is detected.

        with PorcupineWakeWordDetector(config) as detector:
            detector.wait_for_wake_word()   # returns only on detection

    The detector owns its own PvRecorder instance, so the microphone is
    exclusively held during the SLEEPING phase and released as soon as the
    context exits — before the caller opens pyaudio for recording.
    """

    def __init__(self, config: PorcupineConfig) -> None:
        self._config = config
        self._porcupine = None
        self._recorder = None
        self._logger = logging.getLogger("guara.wake_word")

    def __enter__(self) -> "PorcupineWakeWordDetector":
        if not self._config.access_key:
            raise ValueError("PORCUPINE_ACCESS_KEY is required.")
        if not self._config.keyword_path:
            raise ValueError("PORCUPINE_KEYWORD_PATH is required.")

        import pvporcupine
        from pvrecorder import PvRecorder

        self._logger.debug("Starting Porcupine wake word detector (sensitivity=%.2f)", self._config.sensitivity)
        self._porcupine = pvporcupine.create(
            access_key=self._config.access_key,
            keyword_paths=[self._config.keyword_path],
            model_path=self._config.model_path or None,
            sensitivities=[self._config.sensitivity],
        )
        self._recorder = PvRecorder(
            frame_length=self._porcupine.frame_length,
            device_index=self._config.audio_device_index,
        )
        self._recorder.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._recorder is not None:
            self._recorder.delete()
            self._recorder = None
        if self._porcupine is not None:
            self._porcupine.delete()
            self._porcupine = None

    def wait_for_wake_word(self) -> None:
        """Block until the configured wake word is detected."""
        if self._porcupine is None or self._recorder is None:
            raise RuntimeError(
                "PorcupineWakeWordDetector must be used as a context manager."
            )
        while True:
            pcm = self._recorder.read()
            if self._porcupine.process(pcm) >= 0:
                self._logger.info("Wake word detected.")
                return
