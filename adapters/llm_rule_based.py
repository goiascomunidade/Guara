from __future__ import annotations

import json
import re
from uuid import uuid4


TOOL_CALL_PATTERN = re.compile(r"^/tool\s+([A-Za-z0-9_:\-]+)\s*(\{.*\})?$")


class RuleBasedLLMProvider:
    """Simple local LLM provider for deterministic orchestration tests."""

    async def complete(self, messages: list[dict], tools=None) -> dict:
        _ = tools
        user_text = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                user_text = str(message.get("content", ""))
                break

        tool_match = TOOL_CALL_PATTERN.match(user_text.strip())
        if tool_match:
            tool_name = tool_match.group(1)
            raw_arguments = tool_match.group(2)
            arguments = {}
            if raw_arguments:
                arguments = json.loads(raw_arguments)
            return {
                "content": f"Executando ferramenta {tool_name}.",
                "tool_calls": [
                    {
                        "call_id": str(uuid4()),
                        "name": tool_name,
                        "arguments": arguments,
                        "run_llm": True,
                    }
                ],
            }

        return {
            "content": f"Você disse: {user_text}",
            "tool_calls": [],
        }

