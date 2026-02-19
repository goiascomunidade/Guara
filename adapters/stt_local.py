from __future__ import annotations


class LocalSTTProvider:
    """Baseline STT provider for local development and tests."""

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        try:
            text = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""

        if text:
            return text

        language_hint = f" ({language})" if language else ""
        return f"<audio:{len(audio)} bytes{language_hint}>"

