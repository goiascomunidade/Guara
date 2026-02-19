from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from core.contracts import IToolProvider
from core.events import EventBus, ToolCalledEvent
from core.tools import ToolCall, ToolExecutionContext, ToolExecutionResult


@dataclass(frozen=True)
class ToolPolicy:
    cancel_on_interruption: bool = True
    timeout_seconds: float = 10.0


@dataclass
class _ActiveCall:
    tool_name: str
    task: asyncio.Task[ToolExecutionResult]
    cancel_on_interruption: bool


class ToolRouter:
    """Runs tool calls with per-tool policies and bounded concurrency."""

    def __init__(self, *, max_parallel_calls: int = 3, event_bus: EventBus | None = None) -> None:
        self._providers: dict[str, IToolProvider] = {}
        self._policies: dict[str, ToolPolicy] = {}
        self._active_calls: dict[str, _ActiveCall] = {}
        self._semaphore = asyncio.Semaphore(max_parallel_calls)
        self._event_bus = event_bus

    def register_tool(self, provider: IToolProvider, policy: ToolPolicy | None = None) -> None:
        self._providers[provider.tool_spec.name] = provider
        self._policies[provider.tool_spec.name] = policy or ToolPolicy()

    def list_tools(self) -> list[str]:
        return sorted(self._providers.keys())

    def get_policy(self, tool_name: str) -> ToolPolicy:
        return self._policies[tool_name]

    def set_tool_policy(self, tool_name: str, policy: ToolPolicy) -> None:
        if tool_name not in self._providers:
            raise KeyError(f"tool not registered: {tool_name}")
        self._policies[tool_name] = policy

    def resolve_tool(self, tool_name: str) -> IToolProvider | None:
        return self._providers.get(tool_name)

    async def execute_calls(
        self,
        calls: list[ToolCall],
        context: ToolExecutionContext,
    ) -> list[ToolExecutionResult]:
        if not calls:
            return []

        if any(call.depends_on for call in calls):
            return await self._execute_dependency_aware(calls, context)
        tasks = [self._spawn_call(call, context) for call in calls]
        return await asyncio.gather(*tasks)

    async def _execute_dependency_aware(
        self,
        calls: list[ToolCall],
        context: ToolExecutionContext,
    ) -> list[ToolExecutionResult]:
        remaining = {call.call_id: call for call in calls}
        completed: dict[str, ToolExecutionResult] = {}

        while remaining:
            ready = [c for c in remaining.values() if c.depends_on.issubset(completed.keys())]
            if not ready:
                pending_ids = ", ".join(sorted(remaining.keys()))
                raise ValueError(f"dependency cycle or missing dependency among calls: {pending_ids}")

            wave = await asyncio.gather(*[self._spawn_call(call, context) for call in ready])
            for result in wave:
                completed[result.call_id] = result
                remaining.pop(result.call_id, None)

        return [completed[call.call_id] for call in calls]

    async def _spawn_call(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        task = asyncio.create_task(self._run_call(call, context))
        policy = self._policies.get(call.function_name, ToolPolicy())
        self._active_calls[call.call_id] = _ActiveCall(
            tool_name=call.function_name,
            task=task,
            cancel_on_interruption=policy.cancel_on_interruption,
        )
        try:
            return await task
        finally:
            self._active_calls.pop(call.call_id, None)

    async def _run_call(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        provider = self._providers.get(call.function_name)
        if not provider:
            return ToolExecutionResult(
                call_id=call.call_id,
                function_name=call.function_name,
                success=False,
                error=f"tool not registered: {call.function_name}",
                run_llm=call.run_llm,
            )

        policy = self._policies.get(call.function_name, ToolPolicy())

        if self._event_bus is not None:
            await self._event_bus.publish(
                ToolCalledEvent(
                    trace_id=context.trace_id,
                    session_id=context.session_id,
                    tool_name=call.function_name,
                    call_id=call.call_id,
                )
            )

        async with self._semaphore:
            try:
                result = await asyncio.wait_for(
                    provider.execute(call.arguments, context),
                    timeout=policy.timeout_seconds,
                )
                return ToolExecutionResult(
                    call_id=call.call_id,
                    function_name=call.function_name,
                    success=True,
                    result=result,
                    run_llm=call.run_llm,
                )
            except asyncio.TimeoutError:
                return ToolExecutionResult(
                    call_id=call.call_id,
                    function_name=call.function_name,
                    success=False,
                    error=f"tool timeout after {policy.timeout_seconds:.2f}s",
                    run_llm=call.run_llm,
                )
            except asyncio.CancelledError:
                return ToolExecutionResult(
                    call_id=call.call_id,
                    function_name=call.function_name,
                    success=False,
                    error="tool call cancelled",
                    run_llm=call.run_llm,
                )
            except Exception as exc:  # pragma: no cover - safeguard
                return ToolExecutionResult(
                    call_id=call.call_id,
                    function_name=call.function_name,
                    success=False,
                    error=str(exc),
                    run_llm=call.run_llm,
                )

    async def cancel_interruptible_calls(self) -> list[str]:
        cancelled: list[str] = []
        for call_id, active in list(self._active_calls.items()):
            if not active.cancel_on_interruption:
                continue
            if active.task.done():
                continue
            active.task.cancel()
            cancelled.append(call_id)
        return cancelled
