from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from core.contracts import IGuardrail, ILLMProvider
from core.tool_runtime import ToolRouter
from core.tools import ToolCall, ToolExecutionContext, ToolExecutionResult

# Max conversation turns kept per session (user+assistant pairs).
_DEFAULT_MAX_HISTORY = 20


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
        system_prompt: str | None = None,
        max_history: int = _DEFAULT_MAX_HISTORY,
    ) -> None:
        self._llm_provider = llm_provider
        self._tool_router = tool_router
        self._guardrail = guardrail
        self._system_prompt = system_prompt
        self._max_history = max_history
        # session_id -> list of {"role": ..., "content": ...}
        self._history: dict[str, list[dict[str, str]]] = defaultdict(list)

    def set_llm_provider(self, llm_provider: ILLMProvider) -> None:
        self._llm_provider = llm_provider

    def clear_history(self, session_id: str) -> None:
        self._history.pop(session_id, None)

    def _build_messages(self, session_id: str, user_text: str) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if self._system_prompt:
            msgs.append({"role": "system", "content": self._system_prompt})
        msgs.extend(self._history[session_id])
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def _record_turn(self, session_id: str, user_text: str, reply_text: str) -> None:
        history = self._history[session_id]
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply_text})
        # Trim oldest turns (keep last N pairs = 2*N messages)
        max_msgs = self._max_history * 2
        if len(history) > max_msgs:
            del history[: len(history) - max_msgs]

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

        tool_specs = self._tool_router.list_tool_specs() or None
        messages = self._build_messages(session_id, user_text)

        llm_result = await self._llm_provider.complete(messages, tools=tool_specs)
        tool_calls = self._extract_tool_calls(llm_result)

        tool_results: list[ToolExecutionResult] = []
        if tool_calls:
            print(f"[DEBUG] LLM pediu {len(tool_calls)} tool(s): {[tc.function_name for tc in tool_calls]}")
            context = ToolExecutionContext(session_id=session_id, trace_id=trace_id, user_id=user_id)
            tool_results = await self._tool_router.execute_calls(tool_calls, context)

            for tr in tool_results:
                status = "OK" if tr.success else f"ERRO: {tr.error}"
                preview = str(tr.result)[:200] if tr.result else "(vazio)"
                print(f"[DEBUG] Tool {tr.function_name}: {status} → {preview}")

            # Feed tool results back to the LLM for a final answer
            tool_messages = list(messages)
            tool_messages.append({"role": "assistant", "content": llm_result.get("content", ""), "tool_calls": llm_result.get("tool_calls", [])})
            for tr in tool_results:
                content = tr.result.get("message", "") if isinstance(tr.result, dict) else str(tr.result or "")
                tool_messages.append({"role": "tool", "tool_call_id": tr.call_id, "content": content})

            print(f"[DEBUG] Enviando {len(tool_messages)} mensagens pro LLM (follow-up)")
            followup = await self._llm_provider.complete(tool_messages, tools=tool_specs)
            print(f"[DEBUG] Follow-up content: {repr(followup.get('content', ''))[:200]}")
            print(f"[DEBUG] Follow-up tool_calls: {followup.get('tool_calls', [])}")
            reply_text = followup.get("content", "") or llm_result.get("content", "")
        else:
            reply_text = llm_result.get("content", "")

        if self._guardrail:
            ok, reason = await self._guardrail.validate_output(reply_text)
            if not ok:
                reply_text = reason or "output blocked"

        self._record_turn(session_id, user_text, reply_text)
        return OrchestratorResponse(reply_text=reply_text, tool_results=tool_results)

    async def stream_user_text(
        self,
        user_text: str,
        *,
        session_id: str,
        trace_id: str,
        user_id: str | None = None,
    ):
        if self._guardrail:
            ok, reason = await self._guardrail.validate_input(user_text)
            if not ok:
                yield reason or "input blocked"
                return

        collected: list[str] = []
        async for token in self._llm_provider.stream(
            self._build_messages(session_id, user_text),
            tools=None,
        ):
            collected.append(token)
            yield token

        self._record_turn(session_id, user_text, "".join(collected))

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
