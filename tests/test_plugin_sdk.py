from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from core.tools import ToolExecutionContext
from plugins.sdk import DirectFunctionToolProvider, PluginLoader, infer_function_schema


def weather(city: str, unit: str = "celsius") -> str:
    """Get weather data for a city."""
    return f"{city}:{unit}"


class TestPluginSDK(unittest.IsolatedAsyncioTestCase):
    def test_infer_function_schema(self) -> None:
        schema = infer_function_schema(weather)
        self.assertEqual(schema.name, "weather")
        self.assertIn("city", schema.properties)
        self.assertIn("city", schema.required)

    async def test_direct_function_tool_provider_executes(self) -> None:
        provider = DirectFunctionToolProvider(weather, name="get_weather")
        result = await provider.execute(
            {"city": "Goiânia", "unit": "celsius"},
            ToolExecutionContext(session_id="s-1", trace_id="t-1"),
        )
        self.assertEqual(result, "Goiânia:celsius")

        with self.assertRaises(ValueError):
            await provider.execute(
                {"unit": "celsius"},
                ToolExecutionContext(session_id="s-1", trace_id="t-1"),
            )

    def test_plugin_loader_validates_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_file = Path(tmp) / "plugin.json"
            manifest_file.write_text(
                json.dumps(
                    {
                        "tool_id": "weather_tool",
                        "name": "weather_tool",
                        "version": "0.1.0",
                        "description": "Weather lookup",
                        "capabilities": ["read"],
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                        "compatibility": {"guara_core": ">=0.1.0,<1.0.0"},
                    }
                )
            )
            loader = PluginLoader(core_version="0.1.5")
            manifest = loader.load(manifest_file)
            self.assertEqual(manifest.name, "weather_tool")
