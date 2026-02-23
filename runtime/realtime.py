from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from typing import Any

from runtime.app import GuaraRuntime
from runtime.ws_protocol import ClientMessage


@dataclass
class RealtimeChannel:
    channel_id: str
    session_id: str
    out_queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    producer_task: asyncio.Task | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RealtimeSessionManager:
    """In-process realtime manager used by websocket transport."""

    def __init__(self, runtime: GuaraRuntime) -> None:
        self._runtime = runtime
        self._channels: dict[str, RealtimeChannel] = {}

    async def open_channel(
        self,
        *,
        channel_id: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> RealtimeChannel:
        sid = session_id or channel_id
        session = self._runtime.session_controller.get_session(sid)
        if session is None:
            await self._runtime.start_session(user_id=user_id, session_id=sid)

        channel = RealtimeChannel(channel_id=channel_id, session_id=sid)
        self._channels[channel_id] = channel
        await channel.out_queue.put({"type": "channel_opened", "channel_id": channel_id, "session_id": sid})
        return channel

    async def close_channel(self, channel_id: str) -> None:
        channel = self._channels.pop(channel_id, None)
        if channel is None:
            return
        if channel.producer_task and not channel.producer_task.done():
            channel.producer_task.cancel()
        await channel.out_queue.put({"type": "channel_closed", "channel_id": channel_id})

    async def recv_event(self, channel_id: str, timeout: float | None = None) -> dict[str, Any]:
        channel = self._require_channel(channel_id)
        if timeout is None:
            return await channel.out_queue.get()
        return await asyncio.wait_for(channel.out_queue.get(), timeout=timeout)

    async def handle_client_message(self, channel_id: str, raw_message: dict[str, Any]) -> None:
        channel = self._require_channel(channel_id)
        message = ClientMessage.from_dict(raw_message)

        if message.type == "text_turn":
            text = str(message.payload.get("text", ""))
            max_chunk_chars = int(message.payload.get("max_chunk_chars", 120))
            stream = self._runtime.stream_text_turn_events(
                channel.session_id,
                text,
                max_chunk_chars=max_chunk_chars,
            )
            await self._start_stream(channel, stream)
            return

        if message.type == "audio_turn":
            audio_base64 = str(message.payload.get("audio_base64", ""))
            language = message.payload.get("language")
            max_chunk_chars = int(message.payload.get("max_chunk_chars", 120))
            audio = base64.b64decode(audio_base64)
            stream = self._runtime.stream_audio_turn_events(
                channel.session_id,
                audio,
                language=language,
                max_chunk_chars=max_chunk_chars,
            )
            await self._start_stream(channel, stream)
            return

        if message.type == "interrupt":
            payload = await self._runtime.interrupt_session(channel.session_id)
            await channel.out_queue.put({"type": "interrupt_result", **payload})
            return

        if message.type == "end":
            payload = await self._runtime.end_session(channel.session_id)
            await channel.out_queue.put({"type": "session_ended", **payload})
            return

        await channel.out_queue.put({"type": "error", "error": f"unsupported message type: {message.type}"})

    async def _start_stream(self, channel: RealtimeChannel, stream) -> None:
        async with channel.lock:
            if channel.producer_task and not channel.producer_task.done():
                await channel.out_queue.put({"type": "error", "error": "turn_in_progress"})
                return
            channel.producer_task = asyncio.create_task(self._forward_stream(channel, stream))

    async def _forward_stream(self, channel: RealtimeChannel, stream) -> None:
        try:
            async for event in stream:
                await channel.out_queue.put(event)
            await channel.out_queue.put({"type": "stream_done"})
        except asyncio.CancelledError:
            await channel.out_queue.put({"type": "stream_cancelled"})
            raise
        except Exception as exc:  # pragma: no cover
            await channel.out_queue.put({"type": "error", "error": str(exc)})

    def _require_channel(self, channel_id: str) -> RealtimeChannel:
        channel = self._channels.get(channel_id)
        if channel is None:
            raise KeyError(f"unknown channel: {channel_id}")
        return channel

