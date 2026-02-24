from __future__ import annotations

import os

from runtime.config import build_runtime
from runtime.listener import WakeWordListener


def build_listener(runtime) -> WakeWordListener:
    """Construct a WakeWordListener from environment variables.

    Env vars:
        GUARA_WAKE_WORD      Word that wakes the assistant (default: "guará").
        GUARA_STOP_WORD      Word that ends recording (default: "obrigado").
        GUARA_VAD_THRESHOLD  Silero VAD confidence threshold (default: "0.5").
    """
    return WakeWordListener(
        runtime,
        wake_word=os.environ.get("GUARA_WAKE_WORD", "guará"),
        stop_word=os.environ.get("GUARA_STOP_WORD", "obrigado"),
        vad_threshold=float(os.environ.get("GUARA_VAD_THRESHOLD", "0.5")),
    )


def main() -> None:
    runtime = build_runtime()
    listener = build_listener(runtime)
    listener.run()


if __name__ == "__main__":
    main()
