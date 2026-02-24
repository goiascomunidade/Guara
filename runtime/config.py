from __future__ import annotations

import os

from runtime.app import GuaraRuntime


def build_runtime() -> GuaraRuntime:
    """Read env vars and build a GuaraRuntime with the configured providers.

    Env vars:
        GUARA_LLM          Which LLM to use (default: "openai").
        GUARA_STT          Which STT to use (default: "whisper").
        GUARA_TTS          Which TTS to use (default: "piper").
        OPENAI_API_KEY     Required when GUARA_LLM=openai.
        OPENAI_MODEL       OpenAI model name (default: "gpt-4o").
        DEEPGRAM_API_KEY   Required when GUARA_STT=deepgram.
        WHISPER_MODEL_SIZE Whisper model size (default: "base").
        PIPER_MODEL_PATH   Path to Piper .onnx model (default: "/models/pt_BR-faber-medium.onnx").
        PIPER_LENGTH_SCALE Piper length scale (default: "1.0").
    """
    guara_llm = os.environ.get("GUARA_LLM", "openai")
    guara_stt = os.environ.get("GUARA_STT", "whisper")
    guara_tts = os.environ.get("GUARA_TTS", "piper")

    # --- Build LLM provider ---
    llm_provider = _build_llm(guara_llm)

    # --- Build STT provider ---
    stt_provider = _build_stt(guara_stt)

    # --- Build TTS provider ---
    tts_provider = _build_tts(guara_tts)

    # Create runtime — this registers "local" defaults and wires the orchestrator
    # with the default rule-based LLM. We then register and activate real providers.
    runtime = GuaraRuntime()

    # Register the real LLM and activate it; also update the orchestrator reference.
    runtime.provider_registry.register(
        kind="llm",
        name=guara_llm,
        provider=llm_provider,
        activate=True,
    )
    runtime.orchestrator.set_llm_provider(runtime.provider_registry.get_active("llm"))

    # Register the real STT provider and activate it.
    runtime.provider_registry.register(
        kind="stt",
        name=guara_stt,
        provider=stt_provider,
        activate=True,
    )

    # Register the real TTS provider and activate it.
    runtime.provider_registry.register(
        kind="tts",
        name=guara_tts,
        provider=tts_provider,
        activate=True,
    )

    return runtime


# ---------------------------------------------------------------------------
# Private builder helpers
# ---------------------------------------------------------------------------

def _build_llm(name: str):
    if name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when GUARA_LLM=openai"
            )
        from adapters.llm_openai import OpenAILLMProvider

        model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        return OpenAILLMProvider(api_key=api_key, model=model)

    raise RuntimeError(f"Unknown GUARA_LLM value: {name!r}")


def _build_stt(name: str):
    if name == "whisper":
        from adapters.stt_whisper import WhisperSTTProvider

        model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")
        return WhisperSTTProvider(model_size=model_size)

    if name == "deepgram":
        api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not api_key:
            raise RuntimeError(
                "DEEPGRAM_API_KEY is required when GUARA_STT=deepgram"
            )
        from adapters.stt_deepgram import DeepgramSTTProvider

        return DeepgramSTTProvider(api_key=api_key)

    raise RuntimeError(f"Unknown GUARA_STT value: {name!r}")


def _build_tts(name: str):
    if name == "piper":
        from adapters.tts_piper import PiperTTSProvider

        model_path = os.environ.get("PIPER_MODEL_PATH", "/models/pt_BR-faber-medium.onnx")
        length_scale = float(os.environ.get("PIPER_LENGTH_SCALE", "1.0"))
        return PiperTTSProvider(model_path=model_path, length_scale=length_scale)

    raise RuntimeError(f"Unknown GUARA_TTS value: {name!r}")
