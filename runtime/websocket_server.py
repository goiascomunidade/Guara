from __future__ import annotations

import asyncio
import contextlib
import json

from runtime.app import GuaraRuntime
from runtime.realtime import RealtimeSessionManager


class GuaraWebSocketServer:
    """Optional websocket transport for full-duplex realtime events."""

    def __init__(self, runtime: GuaraRuntime | None = None) -> None:
        self.runtime = runtime or GuaraRuntime()
        self.manager = RealtimeSessionManager(self.runtime)

    async def serve(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        try:
            from websockets.server import serve
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "websockets package is required for websocket transport. "
                "Install with: pip install websockets"
            ) from exc

        async with serve(self._handle_connection, host, port):
            await asyncio.Future()

    async def _handle_connection(self, websocket, path: str | None = None) -> None:
        resolved_path = path if path is not None else getattr(websocket, "path", "/")
        channel_id, session_id = self._parse_path(resolved_path)
        await self.manager.open_channel(channel_id=channel_id, session_id=session_id)

        sender_task = asyncio.create_task(self._sender_loop(channel_id, websocket))
        receiver_task = asyncio.create_task(self._receiver_loop(channel_id, websocket))

        done, pending = await asyncio.wait(
            {sender_task, receiver_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            with contextlib.suppress(Exception):
                await task
        await self.manager.close_channel(channel_id)

    async def _receiver_loop(self, channel_id: str, websocket) -> None:
        async for raw in websocket:
            message = json.loads(raw)
            await self.manager.handle_client_message(channel_id, message)

    async def _sender_loop(self, channel_id: str, websocket) -> None:
        while True:
            event = await self.manager.recv_event(channel_id)
            await websocket.send(json.dumps(event, ensure_ascii=True))
            if event.get("type") in {"channel_closed", "session_ended"}:
                return

    @staticmethod
    def _parse_path(path: str) -> tuple[str, str]:
        # Expected: /ws/{session_id}
        parts = [item for item in path.split("/") if item]
        if len(parts) >= 2 and parts[0] == "ws":
            session_id = parts[1]
            return session_id, session_id
        return "default-channel", "default-channel"
