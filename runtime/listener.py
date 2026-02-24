from __future__ import annotations

import asyncio
import base64
import io
import subprocess
import unicodedata
import wave
from enum import Enum, auto

import numpy as np
import pyaudio

from adapters.wakeword_vad import SpeechActivityDetector
from runtime.app import GuaraRuntime


class _State(Enum):
    SLEEPING = auto()
    RECORDING = auto()
    SENDING = auto()


def _pcm_to_wav(frames: list[bytes], rate: int = 16000) -> bytes:
    """Wrap raw 16-bit mono PCM frames into a WAV byte string."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))
    return buf.getvalue()


def _beep(freq: int = 440, duration_ms: int = 150, rate: int = 22050) -> None:
    """Play a short sine-wave beep via aplay."""
    t = np.linspace(0, duration_ms / 1000, int(rate * duration_ms / 1000), endpoint=False)
    samples = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    try:
        subprocess.run(
            ["aplay", "-q", "-r", str(rate), "-f", "S16_LE", "-c", "1"],
            input=samples.tobytes(),
            stderr=subprocess.DEVNULL,
            timeout=duration_ms / 1000 + 1,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # aplay not available or timed out


def _play_audio(pcm_bytes: bytes, rate: int = 22050) -> None:
    """Play raw 16-bit mono PCM audio via aplay."""
    try:
        subprocess.run(
            ["aplay", "-q", "-r", str(rate), "-f", "S16_LE", "-c", "1"],
            input=pcm_bytes,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # aplay not available or timed out


class WakeWordListener:
    """Continuous microphone listener with VAD gate and Whisper wake/stop word detection.

    States:
        SLEEPING  — VAD filters silence; when speech detected, runs Whisper to
                    check for wake word in a 1.5s window.
        RECORDING — Accumulates audio; Whisper checks every 2s for the stop word.
        SENDING   — Full audio sent to GuaraRuntime; response played; back to SLEEPING.
    """

    _VAD_CHECK_FRAMES = 50   # 50 × 30ms = 1.5s
    _STT_CHECK_FRAMES = 67   # 67 × 30ms ≈ 2.0s

    def __init__(
        self,
        runtime: GuaraRuntime,
        *,
        wake_word: str = "guará",
        stop_word: str = "obrigado",
        vad_threshold: float = 0.5,
    ) -> None:
        self._runtime = runtime
        self.wake_word = wake_word.lower()
        self.stop_word = stop_word.lower()
        self._vad = SpeechActivityDetector(threshold=vad_threshold)
        self._session_id: str | None = None

    @staticmethod
    def _normalize(s: str) -> str:
        """Strip accents so 'guará' and 'guara' both match."""
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower()

    def _check_for_word(self, text: str, word: str) -> bool:
        return self._normalize(word) in self._normalize(text)

    def _transcribe_sync(self, frames: list[bytes]) -> str:
        wav = _pcm_to_wav(frames)
        stt = self._runtime.stt_provider
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(stt.transcribe(wav, language="pt"))
        finally:
            loop.close()

    def run(self) -> None:
        """Blocking main loop. Run in main thread or a dedicated process."""
        self._session_id = asyncio.run(
            self._runtime.start_session()
        )["session_id"]

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=480,
        )

        frame = b""
        state = _State.SLEEPING
        window: list[bytes] = []
        recording: list[bytes] = []

        print(f"Aguardando '{self.wake_word}'...")

        try:
            while True:
                if state != _State.SENDING:
                    frame = stream.read(480, exception_on_overflow=False)

                if state == _State.SLEEPING:
                    window.append(frame)
                    if len(window) >= self._VAD_CHECK_FRAMES:
                        combined = b"".join(window)
                        if self._vad.is_speech(combined):
                            text = self._transcribe_sync(window)
                            if self._check_for_word(text, self.wake_word):
                                print(
                                    f"Wake word detectado! Gravando... "
                                    f"(diga '{self.stop_word}' para encerrar)"
                                )
                                _beep(440, 150)
                                self._vad.reset()
                                recording = []
                                state = _State.RECORDING
                        window = []

                elif state == _State.RECORDING:
                    recording.append(frame)
                    if len(recording) % self._STT_CHECK_FRAMES == 0:
                        text = self._transcribe_sync(recording[-self._STT_CHECK_FRAMES:])
                        if self._check_for_word(text, self.stop_word):
                            print("Stop word detectado. Enviando...")
                            _beep(660, 100)
                            _beep(660, 100)
                            state = _State.SENDING

                elif state == _State.SENDING:
                    wav = _pcm_to_wav(recording)
                    try:
                        result = asyncio.run(
                            self._runtime.process_audio_turn(
                                self._session_id, wav, language="pt"
                            )
                        )
                        print(f"Você disse: {result.get('transcript', '')}")
                        print(f"Guará: {result.get('reply_text', '')}")
                        audio_b64 = result.get("audio_base64", "")
                        if audio_b64:
                            _play_audio(base64.b64decode(audio_b64))
                    except Exception as exc:
                        print(f"Erro ao processar turno: {exc}")
                        _beep(220, 400)

                    recording = []
                    window = []
                    state = _State.SLEEPING
                    print(f"\nAguardando '{self.wake_word}'...")

        except KeyboardInterrupt:
            print("\nEncerrando listener.")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
