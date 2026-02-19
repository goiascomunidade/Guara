from __future__ import annotations


class LocalTTSProvider:
    """Baseline TTS provider for local development and tests."""

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        payload = text if voice is None else f"[{voice}] {text}"
        return payload.encode("utf-8")

