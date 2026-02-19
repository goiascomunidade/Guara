from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.contracts import IGuardrail, ILLMProvider
from core.tool_runtime import ToolRouter
from core.tools import ToolCall, ToolExecutionContext, ToolExecutionResult


@dataclass(frozen=True)
class OrchestratorResponse:
    reply_text: str
    tool_results: list[ToolExecutionResult]


class Orchestrator:
    """Minimal orchestration layer for text+tools execution."""

    def __init__(
        self,
        llm_provider: ILLMProvider,
        tool_router: ToolRouter,
        guardrail: IGuardrail | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._tool_router = tool_router
        self._guardrail = guardrail

    def set_llm_provider(self, llm_provider: ILLMProvider) -> None:
        self._llm_provider = llm_provider

    async def handle_user_text(
        self,
        user_text: str,
        *,
        session_id: str,
        trace_id: str,
        user_id: str | None = None,
    ) -> OrchestratorResponse:
        if self._guardrail:
            ok, reason = await self._guardrail.validate_input(user_text)
            if not ok:
                return OrchestratorResponse(reply_text=reason or "input blocked", tool_results=[])

        llm_result = await self._llm_provider.complete(
            [{"role": "user", "content": user_text}],
            tools=None,
        )
        tool_calls = self._extract_tool_calls(llm_result)

        tool_results: list[ToolExecutionResult] = []
        if tool_calls:
            context = ToolExecutionContext(session_id=session_id, trace_id=trace_id, user_id=user_id)
            tool_results = await self._tool_router.execute_calls(tool_calls, context)

        reply_text = llm_result.get("content", "")
        if self._guardrail:
            ok, reason = await self._guardrail.validate_output(reply_text)
            if not ok:
                reply_text = reason or "output blocked"

        return OrchestratorResponse(reply_text=reply_text, tool_results=tool_results)

    def _extract_tool_calls(self, llm_result: dict[str, Any]) -> list[ToolCall]:
        raw_calls = llm_result.get("tool_calls", [])
        calls: list[ToolCall] = []
        for raw in raw_calls:
            calls.append(
                ToolCall(
                    call_id=str(raw["call_id"]),
                    function_name=str(raw["name"]),
                    arguments=dict(raw.get("arguments", {})),
                    depends_on=set(raw.get("depends_on", [])),
                    run_llm=bool(raw.get("run_llm", True)),
                )
            )
        return calls
