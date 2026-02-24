from __future__ import annotations

from collections.abc import AsyncIterator


class LocalTTSProvider:
    """Baseline TTS provider for local development and tests."""

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        payload = text if voice is None else f"[{voice}] {text}"
        return payload.encode("utf-8")

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        async for token in text_stream:
            payload = token if voice is None else f"[{voice}] {token}"
            yield payload.encode("utf-8")

    async def cancel(self, session_id: str) -> None:
        """No-op: local TTS has no active synthesis to cancel."""
