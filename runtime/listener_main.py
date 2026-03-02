from __future__ import annotations

import os

from dotenv import load_dotenv

from adapters.wakeword_porcupine import PorcupineConfig
from runtime.config import build_runtime
from runtime.listener import WakeWordListener


def build_listener(runtime) -> WakeWordListener:
    """Construct a WakeWordListener from environment variables.

    Env vars:
        PORCUPINE_ACCESS_KEY    Picovoice access key (required).
        PORCUPINE_KEYWORD_PATH  Path to .ppn keyword file for "guará" (required).
        PORCUPINE_MODEL_PATH    Path to Porcupine model file (optional).
        PORCUPINE_SENSITIVITY   Detection sensitivity 0.0–1.0 (default: "0.5").
        PORCUPINE_DEVICE_INDEX  Audio device index (default: "-1").
        GUARA_WAKE_WORD         Display label for the wake word (default: "guará").
        GUARA_STOP_WORD         Word that ends recording (default: "obrigado").
    """
    porcupine_config = PorcupineConfig(
        access_key=os.environ.get("PORCUPINE_ACCESS_KEY", ""),
        keyword_path=os.environ.get("PORCUPINE_KEYWORD_PATH", ""),
        model_path=os.environ.get("PORCUPINE_MODEL_PATH", ""),
        sensitivity=float(os.environ.get("PORCUPINE_SENSITIVITY", "0.5")),
        audio_device_index=int(os.environ.get("PORCUPINE_DEVICE_INDEX", "-1")),
    )
    return WakeWordListener(
        runtime,
        porcupine_config=porcupine_config,
        wake_word=os.environ.get("GUARA_WAKE_WORD", "guará"),
        stop_word=os.environ.get("GUARA_STOP_WORD", "obrigado"),
    )


def main() -> None:
    load_dotenv()
    runtime = build_runtime()
    listener = build_listener(runtime)
    listener.run()


if __name__ == "__main__":
    main()
