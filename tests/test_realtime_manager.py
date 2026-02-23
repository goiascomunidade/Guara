from __future__ import annotations

import asyncio
import base64
import unittest

from runtime.app import GuaraRuntime
from runtime.realtime import RealtimeSessionManager


class TestRealtimeSessionManager(unittest.IsolatedAsyncioTestCase):
    async def test_text_turn_message_emits_stream_events(self) -> None:
        runtime = GuaraRuntime()
        manager = RealtimeSessionManager(runtime)
        await manager.open_channel(channel_id="c1", session_id="s1")

        # Drain channel_opened
        first = await manager.recv_event("c1")
        self.assertEqual(first["type"], "channel_opened")

        await manager.handle_client_message(
            "c1",
            {"type": "text_turn", "text": "teste realtime", "max_chunk_chars": 10},
        )

        collected = []
        for _ in range(30):
            event = await manager.recv_event("c1", timeout=1.0)
            collected.append(event)
            if event.get("type") == "stream_done":
                break

        event_types = [item["type"] for item in collected]
        self.assertIn("turn_started", event_types)
        self.assertIn("llm_chunk", event_types)
        self.assertIn("tts_chunk", event_types)
        self.assertIn("turn_completed", event_types)
        self.assertEqual(event_types[-1], "stream_done")

    async def test_audio_turn_message_emits_transcript(self) -> None:
        runtime = GuaraRuntime()
        manager = RealtimeSessionManager(runtime)
        await manager.open_channel(channel_id="c2", session_id="s2")
        await manager.recv_event("c2")  # channel_opened

        await manager.handle_client_message(
            "c2",
            {
                "type": "audio_turn",
                "audio_base64": base64.b64encode(b"audio canal").decode("ascii"),
                "language": "pt-BR",
                "max_chunk_chars": 12,
            },
        )

        transcript = None
        for _ in range(40):
            event = await manager.recv_event("c2", timeout=1.0)
            if event.get("type") == "transcript":
                transcript = event.get("text")
            if event.get("type") == "stream_done":
                break

        self.assertIsNotNone(transcript)
        self.assertTrue(transcript)

    async def test_interrupt_message_returns_result(self) -> None:
        runtime = GuaraRuntime()
        manager = RealtimeSessionManager(runtime)
        await manager.open_channel(channel_id="c3", session_id="s3")
        await manager.recv_event("c3")  # channel_opened

        await manager.handle_client_message("c3", {"type": "interrupt"})
        event = await manager.recv_event("c3", timeout=1.0)
        self.assertEqual(event["type"], "interrupt_result")
        self.assertEqual(event["session_id"], "s3")

    async def test_turn_in_progress_error(self) -> None:
        runtime = GuaraRuntime()
        manager = RealtimeSessionManager(runtime)
        await manager.open_channel(channel_id="c4", session_id="s4")
        await manager.recv_event("c4")  # channel_opened

        await manager.handle_client_message("c4", {"type": "text_turn", "text": "primeiro"})
        await manager.handle_client_message("c4", {"type": "text_turn", "text": "segundo"})

        saw_in_progress = False
        for _ in range(40):
            event = await manager.recv_event("c4", timeout=1.0)
            if event.get("type") == "error" and event.get("error") == "turn_in_progress":
                saw_in_progress = True
            if event.get("type") == "stream_done":
                break
        self.assertTrue(saw_in_progress)

