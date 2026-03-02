"""Tests for the DuckDuckGo web search tool adapters."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from adapters.tool_websearch import DuckDuckGoNewsTool, DuckDuckGoSearchTool
from core.tools import ToolExecutionContext

CTX = ToolExecutionContext(session_id="s-1", trace_id="t-1")


class TestDuckDuckGoSearchTool(unittest.IsolatedAsyncioTestCase):
    def test_tool_spec(self) -> None:
        tool = DuckDuckGoSearchTool()
        spec = tool.tool_spec
        self.assertEqual(spec.id, "web_search")
        self.assertEqual(spec.name, "web_search")
        self.assertIn("query", spec.input_schema["properties"])
        self.assertIn("query", spec.input_schema["required"])

    async def test_empty_query_returns_error(self) -> None:
        tool = DuckDuckGoSearchTool()
        result = await tool.execute({"query": "  "}, CTX)
        self.assertEqual(result["data"]["error"], "empty_query")

    async def test_missing_dependency_returns_error(self) -> None:
        tool = DuckDuckGoSearchTool()
        with patch.dict("sys.modules", {"duckduckgo_search": None}):
            result = await tool.execute({"query": "test"}, CTX)
        self.assertEqual(result["data"]["error"], "missing_dependency")

    async def test_search_returns_results(self) -> None:
        fake_results = [
            {"title": "Result 1", "href": "https://example.com/1", "body": "Snippet 1"},
            {"title": "Result 2", "href": "https://example.com/2", "body": "Snippet 2"},
        ]

        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = fake_results

        with patch("adapters.tool_websearch.DDGS", return_value=mock_ddgs, create=True):
            # Need to re-import so the patched import takes effect inside execute
            pass

        # Patch at the point of import inside execute
        import duckduckgo_search as _mod

        original_ddgs = getattr(_mod, "DDGS", None)
        _mod.DDGS = lambda **kw: mock_ddgs
        try:
            tool = DuckDuckGoSearchTool()
            result = await tool.execute({"query": "python"}, CTX)
        finally:
            if original_ddgs is not None:
                _mod.DDGS = original_ddgs

        self.assertEqual(result["data"]["result_count"], 2)
        self.assertEqual(result["data"]["results"][0]["title"], "Result 1")
        self.assertEqual(result["data"]["results"][0]["url"], "https://example.com/1")
        self.assertIn("python", result["data"]["query"])

    async def test_search_no_results(self) -> None:
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = []

        import duckduckgo_search as _mod

        original_ddgs = getattr(_mod, "DDGS", None)
        _mod.DDGS = lambda **kw: mock_ddgs
        try:
            tool = DuckDuckGoSearchTool()
            result = await tool.execute({"query": "xyznonexistent"}, CTX)
        finally:
            if original_ddgs is not None:
                _mod.DDGS = original_ddgs

        self.assertEqual(result["data"]["results"], [])
        self.assertIn("Nenhum resultado", result["message"])

    async def test_custom_max_results(self) -> None:
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": f"R{i}", "href": f"https://example.com/{i}", "body": f"S{i}"}
            for i in range(3)
        ]

        import duckduckgo_search as _mod

        original_ddgs = getattr(_mod, "DDGS", None)
        _mod.DDGS = lambda **kw: mock_ddgs
        try:
            tool = DuckDuckGoSearchTool()
            result = await tool.execute({"query": "test", "max_results": 3}, CTX)
        finally:
            if original_ddgs is not None:
                _mod.DDGS = original_ddgs

        mock_ddgs.text.assert_called_once()
        call_kwargs = mock_ddgs.text.call_args
        self.assertEqual(call_kwargs.kwargs.get("max_results"), 3)


class TestDuckDuckGoNewsTool(unittest.IsolatedAsyncioTestCase):
    def test_tool_spec(self) -> None:
        tool = DuckDuckGoNewsTool()
        spec = tool.tool_spec
        self.assertEqual(spec.id, "news_search")
        self.assertEqual(spec.name, "news_search")
        self.assertIn("query", spec.input_schema["properties"])

    async def test_empty_query_returns_error(self) -> None:
        tool = DuckDuckGoNewsTool()
        result = await tool.execute({"query": ""}, CTX)
        self.assertEqual(result["data"]["error"], "empty_query")

    async def test_news_returns_results(self) -> None:
        fake_results = [
            {
                "title": "Breaking News",
                "url": "https://news.example.com/1",
                "body": "Something happened",
                "source": "Example News",
                "date": "2026-03-01T10:00:00+00:00",
            },
        ]

        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.news.return_value = fake_results

        import duckduckgo_search as _mod

        original_ddgs = getattr(_mod, "DDGS", None)
        _mod.DDGS = lambda **kw: mock_ddgs
        try:
            tool = DuckDuckGoNewsTool()
            result = await tool.execute({"query": "tech"}, CTX)
        finally:
            if original_ddgs is not None:
                _mod.DDGS = original_ddgs

        self.assertEqual(result["data"]["result_count"], 1)
        self.assertEqual(result["data"]["results"][0]["source"], "Example News")
        self.assertIn("tech", result["data"]["query"])
