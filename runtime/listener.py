from __future__ import annotations

import asyncio
import base64
import ctypes
import io
import os
import subprocess
import traceback
import unicodedata
import wave

import numpy as np
import pyaudio

from adapters.wakeword_porcupine import PorcupineConfig, PorcupineWakeWordDetector
from runtime.app import GuaraRuntime


def _suppress_audio_warnings() -> None:
    """Suppress ALSA and JACK warnings that PyAudio triggers on init.

    PyAudio enumerates all audio devices, producing harmless but noisy
    warnings from ALSA (pcm_dmix, pcm_dsnoop, etc.) and JACK (server
    not running).  This silences both by:
    - Setting ALSA's error handler to a no-op via ctypes.
    - Setting JACK_NO_START_SERVER=1 so libjack won't try to connect.
    """
    # Suppress JACK "Cannot connect to server" messages
    os.environ["JACK_NO_START_SERVER"] = "1"
    os.environ["JACK_NO_AUDIO_RESERVATION"] = "1"

    # Suppress ALSA warnings
    try:
        asound = ctypes.cdll.LoadLibrary("libasound.so.2")
        c_error_handler = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int,
                                           ctypes.c_char_p, ctypes.c_int,
                                           ctypes.c_char_p)
        _noop_handler = c_error_handler(lambda *_: None)
        asound.snd_lib_error_set_handler(_noop_handler)
        _suppress_audio_warnings._handler = _noop_handler  # type: ignore[attr-defined]
    except OSError:
        pass

    # Suppress JACK client-side messages via libjack
    try:
        libjack = ctypes.cdll.LoadLibrary("libjack.so.0")
        c_jack_handler = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
        _noop_jack = c_jack_handler(lambda *_: None)
        libjack.jack_set_error_function(_noop_jack)
        libjack.jack_set_info_function(_noop_jack)
        _suppress_audio_warnings._jack_handler = _noop_jack  # type: ignore[attr-defined]
    except OSError:
        pass


_suppress_audio_warnings()


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
    """Continuous microphone listener using Porcupine wake word detection.

    Flow:
        SLEEPING  — PorcupineWakeWordDetector (PvRecorder) blocks until the
                    trained keyword is detected. No Whisper involved here.
        RECORDING — pyaudio accumulates audio; Whisper checks every ~2s for
                    the stop word that ends the recording.
        SENDING   — Full audio sent to GuaraRuntime; response played; back to SLEEPING.

    The microphone is released between phases: PvRecorder is deleted before
    pyaudio opens, avoiding device conflicts on ALSA/PipeWire.
    """

    _STT_CHECK_FRAMES = 67  # 67 × 30ms ≈ 2.0s

    def __init__(
        self,
        runtime: GuaraRuntime,
        *,
        porcupine_config: PorcupineConfig,
        wake_word: str = "guará",
        stop_word: str = "obrigado",
    ) -> None:
        self._runtime = runtime
        self._porcupine_config = porcupine_config
        self.wake_word = wake_word
        self.stop_word = stop_word.lower()
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

    def _record_until_stop_word(self) -> list[bytes]:
        """Open mic via pyaudio and accumulate frames until stop word detected."""
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=480,
        )
        recording: list[bytes] = []
        try:
            while True:
                frame = stream.read(480, exception_on_overflow=False)
                recording.append(frame)
                if len(recording) % self._STT_CHECK_FRAMES == 0:
                    text = self._transcribe_sync(recording[-self._STT_CHECK_FRAMES:])
                    if self._check_for_word(text, self.stop_word):
                        return recording
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def run(self) -> None:
        """Blocking main loop. Run in main thread or a dedicated process."""
        self._session_id = asyncio.run(
            self._runtime.start_session()
        )["session_id"]

        print(f"Aguardando '{self.wake_word}'...")
        try:
            while True:
                # SLEEPING: Porcupine holds PvRecorder and blocks until wake word
                with PorcupineWakeWordDetector(self._porcupine_config) as detector:
                    detector.wait_for_wake_word()
                # PvRecorder is now deleted — safe to open pyaudio below

                print(
                    f"Wake word detectado! Gravando... "
                    f"(diga '{self.stop_word}' para encerrar)"
                )
                _beep(440, 150)

                try:
                    # RECORDING: pyaudio accumulates until stop word
                    recording = self._record_until_stop_word()

                    print("Stop word detectado. Enviando...")
                    _beep(660, 100)
                    _beep(660, 100)

                    # SENDING
                    wav = _pcm_to_wav(recording)
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
                    print(f"Erro no turno: {exc}")
                    traceback.print_exc()
                    _beep(220, 400)

                print(f"\nAguardando '{self.wake_word}'...")

        except KeyboardInterrupt:
            print("\nEncerrando listener.")
