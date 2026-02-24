from __future__ import annotations

import asyncio
import unittest

from core.events import EventBus
from core.session import SessionController
from core.tool_runtime import ToolPolicy, ToolRouter
from core.tools import ToolCall, ToolExecutionContext, ToolSpec
from core.types import RiskLevel, SessionState


class _LongTool:
    @property
    def tool_spec(self) -> ToolSpec:
        return ToolSpec(
            id="long",
            name="long",
            description="long operation",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk_level=RiskLevel.LOW,
        )

    async def execute(self, arguments, context):
        await asyncio.sleep(2.0)
        return {"done": True}


class TestSessionController(unittest.IsolatedAsyncioTestCase):
    async def test_session_interrupt_cancels_running_tools(self) -> None:
        bus = EventBus()
        router = ToolRouter(max_parallel_calls=1, event_bus=bus)
        router.register_tool(
            _LongTool(),
            policy=ToolPolicy(cancel_on_interruption=True, timeout_seconds=5),
        )
        controller = SessionController(event_bus=bus, tool_router=router)

        await controller.start_session("s-1", user_id="u-1")
        turn_id = await controller.push_audio_frame("s-1", b"audio")
        self.assertTrue(turn_id)
        self.assertEqual(controller.get_session("s-1").state, SessionState.THINKING)

        call_task = asyncio.create_task(
            router.execute_calls(
                [ToolCall(call_id="call-1", function_name="long", arguments={})],
                ToolExecutionContext(session_id="s-1", trace_id="trace-1"),
            )
        )
        await asyncio.sleep(0.05)
        cancelled = await controller.interrupt("s-1")
        results = await call_task

        self.assertIn("call-1", cancelled)
        self.assertFalse(results[0].success)
        self.assertEqual(controller.get_session("s-1").state, SessionState.LISTENING)
