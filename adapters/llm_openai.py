from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI


class OpenAILLMProvider:
    """LLM adapter for OpenAI chat completions API."""

    def __init__(self, *, api_key: str, model: str = "gpt-4o") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Any | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"model": self._model, "messages": self._convert_messages(messages)}
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        result: dict[str, Any] = {"content": message.content or "", "tool_calls": []}
        if message.tool_calls:
            for tc in message.tool_calls:
                result["tool_calls"].append({
                    "call_id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                    "run_llm": True,
                })
        return result

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Any | None = None,
    ) -> AsyncIterator[str]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        async with self._client.chat.completions.create(**kwargs) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert internal message format to OpenAI chat format.

        Handles assistant messages with tool_calls (internal → OpenAI format)
        and tool result messages.
        """
        converted = []
        for msg in messages:
            role = msg.get("role")
            if role == "assistant" and "tool_calls" in msg and msg["tool_calls"]:
                oai_tool_calls = []
                for tc in msg["tool_calls"]:
                    # Already in OpenAI format (has "type" key)
                    if "type" in tc:
                        oai_tool_calls.append(tc)
                    else:
                        # Internal format → OpenAI format
                        args = tc.get("arguments", {})
                        oai_tool_calls.append({
                            "id": tc.get("call_id", tc.get("id", "")),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                            },
                        })
                converted.append({
                    "role": "assistant",
                    "content": msg.get("content") or None,
                    "tool_calls": oai_tool_calls,
                })
            elif role == "tool":
                converted.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": str(msg.get("content", "")),
                })
            else:
                converted.append(msg)
        return converted

    def _convert_tools(self, tools: Any) -> list[dict[str, Any]]:
        """Convert ToolSpec list to OpenAI function-calling format."""
        if not isinstance(tools, list):
            return []
        result = []
        for tool in tools:
            if hasattr(tool, "name") and hasattr(tool, "description"):
                result.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": getattr(tool, "input_schema", {"type": "object"}),
                    },
                })
        return result
