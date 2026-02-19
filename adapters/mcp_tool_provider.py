from __future__ import annotations

from typing import Any

from adapters.mcp_http import MCPHTTPClient
from core.contracts import IToolProvider
from core.tools import ToolExecutionContext, ToolSpec
from core.types import RiskLevel


def _normalize_input_schema(tool: dict[str, Any]) -> dict[str, Any]:
    if "input_schema" in tool and isinstance(tool["input_schema"], dict):
        return dict(tool["input_schema"])
    if "inputSchema" in tool and isinstance(tool["inputSchema"], dict):
        return dict(tool["inputSchema"])
    return {"type": "object", "properties": {}, "required": []}


class MCPToolProvider(IToolProvider):
    """Tool provider backed by a remote MCP HTTP server."""

    def __init__(self, client: MCPHTTPClient, tool_definition: dict[str, Any]) -> None:
        self._client = client
        self._tool_name = str(tool_definition["name"])
        input_schema = _normalize_input_schema(tool_definition)
        description = str(tool_definition.get("description", f"MCP tool {self._tool_name}"))
        self._tool_spec = ToolSpec(
            id=f"mcp:{self._tool_name}",
            name=self._tool_name,
            description=description,
            input_schema=input_schema,
            output_schema={"type": "object"},
            risk_level=RiskLevel.LOW,
        )

    @property
    def tool_spec(self) -> ToolSpec:
        return self._tool_spec

    async def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> Any:
        _ = context
        return await self._client.call_tool(self._tool_name, arguments)


async def discover_mcp_tool_providers(
    client: MCPHTTPClient,
    *,
    allowlist: set[str] | None = None,
) -> list[MCPToolProvider]:
    providers: list[MCPToolProvider] = []
    tools = await client.list_tools()
    for tool in tools:
        name = str(tool.get("name", ""))
        if not name:
            continue
        if allowlist is not None and name not in allowlist:
            continue
        providers.append(MCPToolProvider(client, tool))
    return providers

