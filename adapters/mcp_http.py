from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from itertools import count
from typing import Any
from urllib import request


@dataclass(frozen=True)
class MCPServerConfig:
    url: str
    auth_token: str | None = None
    timeout_seconds: float = 5.0


class MCPHTTPClient:
    """Minimal JSON-RPC HTTP client for MCP-compatible servers."""

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._request_id = count(1)

    async def ping(self) -> bool:
        try:
            await self._rpc("ping", {})
            return True
        except Exception:
            return False

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._rpc("list_tools", {})
        if isinstance(result, dict):
            tools = result.get("tools")
            if isinstance(tools, list):
                return [dict(item) for item in tools]
        if isinstance(result, list):
            return [dict(item) for item in result]
        raise RuntimeError(f"invalid list_tools response: {result!r}")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._rpc("call_tool", {"name": name, "arguments": arguments})
        if isinstance(result, dict) and "content" in result:
            chunks = result.get("content", [])
            if isinstance(chunks, list):
                texts = []
                for chunk in chunks:
                    if isinstance(chunk, dict) and "text" in chunk:
                        texts.append(str(chunk["text"]))
                if texts:
                    return "\n".join(texts)
        return result

    async def _rpc(self, method: str, params: dict[str, Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_id),
            "method": method,
            "params": params,
        }
        return await asyncio.to_thread(self._post, payload)

    def _post(self, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._config.auth_token:
            headers["Authorization"] = f"Bearer {self._config.auth_token}"
        req = request.Request(self._config.url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=self._config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        parsed = json.loads(raw)
        if "error" in parsed and parsed["error"]:
            raise RuntimeError(str(parsed["error"]))
        if "result" not in parsed:
            raise RuntimeError("invalid RPC response: missing result")
        return parsed["result"]

