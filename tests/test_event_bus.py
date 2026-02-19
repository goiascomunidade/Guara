from __future__ import annotations

import unittest

from core.events import EventBus, TurnStartedEvent


class TestEventBus(unittest.IsolatedAsyncioTestCase):
    async def test_event_bus_dispatches_typed_event(self) -> None:
        bus = EventBus()
        seen = []

        async def handler(record):
            seen.append(record)

        await bus.subscribe("turn_started", handler)
        await bus.publish(TurnStartedEvent(trace_id="t-1", session_id="s-1", turn_id="turn-1"))

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].event_name, "turn_started")
        self.assertEqual(seen[0].event_version, 1)
        self.assertEqual(seen[0].payload["turn_id"], "turn-1")
