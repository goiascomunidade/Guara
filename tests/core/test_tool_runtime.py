from __future__ import annotations

import asyncio
from dataclasses import dataclass
import unittest

from core.contracts import IToolProvider
from core.tool_runtime import ToolPolicy, ToolRouter
from core.tools import ToolCall, ToolExecutionContext, ToolSpec
from core.types import RiskLevel


@dataclass
class _ConcurrencyTracker:
    active: int = 0
    max_seen: int = 0


class SleepTool(IToolProvider):
    def __init__(self, name: str, delay: float, tracker: _ConcurrencyTracker) -> None:
        self._name = name
        self._delay = delay
        self._tracker = tracker
        self._order: list[str] = []

    @property
    def order(self) -> list[str]:
        return self._order

    @property
    def tool_spec(self) -> ToolSpec:
        return ToolSpec(
            id=self._name,
            name=self._name,
            description="sleep tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk_level=RiskLevel.LOW,
        )

    async def execute(self, arguments: dict, _: ToolExecutionContext):
        call_id = arguments.get("call_id", "")
        self._order.append(call_id)
        self._tracker.active += 1
        self._tracker.max_seen = max(self._tracker.max_seen, self._tracker.active)
        try:
            await asyncio.sleep(self._delay)
            return {"ok": True, "call_id": call_id}
        finally:
            self._tracker.active -= 1


class TestToolRuntime(unittest.IsolatedAsyncioTestCase):
    async def test_tool_router_respects_parallel_limit(self) -> None:
        tracker = _ConcurrencyTracker()
        tool = SleepTool("sleep", 0.03, tracker)
        router = ToolRouter(max_parallel_calls=2)
        router.register_tool(tool)

        ctx = ToolExecutionContext(session_id="s1", trace_id="t1")
        calls = [
            ToolCall(call_id=f"c{i}", function_name="sleep", arguments={"call_id": f"c{i}"})
            for i in range(6)
        ]
        results = await router.execute_calls(calls, ctx)

        self.assertEqual(len(results), 6)
        self.assertTrue(all(item.success for item in results))
        self.assertLessEqual(tracker.max_seen, 2)

    async def test_tool_router_cancels_interruptible_calls(self) -> None:
        tracker = _ConcurrencyTracker()
        tool = SleepTool("slow", 2.0, tracker)
        router = ToolRouter(max_parallel_calls=1)
        router.register_tool(tool, policy=ToolPolicy(cancel_on_interruption=True, timeout_seconds=5))

        ctx = ToolExecutionContext(session_id="s1", trace_id="t2")
        calls = [
            ToolCall(call_id="cancel-me", function_name="slow", arguments={"call_id": "cancel-me"})
        ]

        running = asyncio.create_task(router.execute_calls(calls, ctx))
        await asyncio.sleep(0.05)
        cancelled_ids = await router.cancel_interruptible_calls()
        results = await running

        self.assertIn("cancel-me", cancelled_ids)
        self.assertFalse(results[0].success)
        self.assertIn("cancelled", results[0].error or "")

    async def test_tool_router_supports_dependency_graph(self) -> None:
        tracker = _ConcurrencyTracker()
        tool = SleepTool("dep_tool", 0.01, tracker)
        router = ToolRouter(max_parallel_calls=4)
        router.register_tool(tool)

        ctx = ToolExecutionContext(session_id="s1", trace_id="t3")
        calls = [
            ToolCall(call_id="c1", function_name="dep_tool", arguments={"call_id": "c1"}),
            ToolCall(
                call_id="c2",
                function_name="dep_tool",
                arguments={"call_id": "c2"},
                depends_on={"c1"},
            ),
        ]
        results = await router.execute_calls(calls, ctx)

        self.assertEqual([result.call_id for result in results], ["c1", "c2"])
        self.assertEqual(tool.order, ["c1", "c2"])
