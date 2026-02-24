from __future__ import annotations

import unittest
from unittest.mock import patch

from adapters.mcp_http import MCPHTTPClient, MCPServerConfig
from runtime.app import GuaraRuntime


async def _mock_rpc(self, method, params):  # noqa: ARG001
    if method == "ping":
        return {"ok": True}
    if method == "list_tools":
        return {
            "tools": [
                {
                    "name": "math_add",
                    "description": "Adds two numbers",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number"},
                            "b": {"type": "number"},
                        },
                        "required": ["a", "b"],
                    },
                }
            ]
        }
    if method == "call_tool" and params.get("name") == "math_add":
        args = params.get("arguments", {})
        return {"content": [{"text": str(float(args["a"]) + float(args["b"]))}]}
    raise RuntimeError(f"unexpected RPC request: {method}")


class TestMCPIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_http_client_list_and_call(self) -> None:
        client = MCPHTTPClient(MCPServerConfig(url="http://unused.test/mcp"))
        with patch.object(MCPHTTPClient, "_rpc", _mock_rpc):
            self.assertTrue(await client.ping())
            tools = await client.list_tools()
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["name"], "math_add")
            result = await client.call_tool("math_add", {"a": 2, "b": 3})
            self.assertEqual(result, "5.0")

    async def test_runtime_registers_mcp_tools_and_executes(self) -> None:
        app = GuaraRuntime()
        with patch.object(MCPHTTPClient, "_rpc", _mock_rpc):
            registration = await app.register_mcp_tools(server_url="http://unused.test/mcp")
            self.assertEqual(registration["registered_count"], 1)
            self.assertIn("math_add", registration["registered_tools"])

            session = await app.start_session(user_id="mcp-user")
            result = await app.process_text_turn(
                session["session_id"],
                '/tool math_add {"a":4,"b":7}',
            )
            self.assertEqual(len(result["tool_results"]), 1)
            self.assertTrue(result["tool_results"][0]["success"])
            self.assertEqual(result["tool_results"][0]["result"], "11.0")

            events = await app.get_events(limit=20, session_id=session["session_id"])
            event_names = {event["event_name"] for event in events["events"]}
            self.assertIn("turn_started", event_names)
            self.assertIn("tool_called", event_names)
            self.assertIn("turn_completed", event_names)
