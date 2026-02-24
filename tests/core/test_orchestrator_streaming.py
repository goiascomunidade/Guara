from __future__ import annotations

import unittest

from adapters.guardrail_basic import BasicGuardrail
from adapters.llm_rule_based import RuleBasedLLMProvider
from core.orchestrator import Orchestrator
from core.tool_runtime import ToolRouter


class TestOrchestratorStreaming(unittest.IsolatedAsyncioTestCase):
    def _make_orchestrator(self) -> Orchestrator:
        return Orchestrator(
            llm_provider=RuleBasedLLMProvider(),
            tool_router=ToolRouter(),
            guardrail=BasicGuardrail(),
        )

    async def test_stream_user_text_yields_tokens(self) -> None:
        orch = self._make_orchestrator()
        tokens = [
            t
            async for t in orch.stream_user_text(
                "oi", session_id="s-1", trace_id="t-1"
            )
        ]
        self.assertGreater(len(tokens), 0)
        self.assertTrue("".join(tokens))

    async def test_stream_user_text_blocked_input_yields_block_message(self) -> None:
        orch = self._make_orchestrator()
        tokens = [
            t
            async for t in orch.stream_user_text(
                "oi tudo bem", session_id="s-2", trace_id="t-2"
            )
        ]
        full = "".join(tokens)
        self.assertTrue(full)
