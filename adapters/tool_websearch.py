"""DuckDuckGo web search tool adapter for Guara."""

from __future__ import annotations

import asyncio
from typing import Any

from core.contracts import IToolProvider
from core.tools import ToolExecutionContext, ToolSpec
from core.types import RiskLevel


class DuckDuckGoSearchTool(IToolProvider):
    """Web search tool backed by the duckduckgo-search library."""

    def __init__(
        self,
        *,
        max_results: int = 5,
        region: str = "wt-wt",
        safesearch: str = "moderate",
        timeout: int = 10,
    ) -> None:
        self._max_results = max_results
        self._region = region
        self._safesearch = safesearch
        self._timeout = timeout
        self._tool_spec = ToolSpec(
            id="web_search",
            name="web_search",
            description=(
                "Search the web using DuckDuckGo. "
                "Returns titles, URLs and snippets for the query."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5).",
                    },
                    "timelimit": {
                        "type": "string",
                        "description": (
                            "Time filter: 'd' (past day), 'w' (past week), "
                            "'m' (past month), 'y' (past year)."
                        ),
                        "enum": ["d", "w", "m", "y"],
                    },
                },
                "required": ["query"],
            },
            output_schema={"type": "object"},
            risk_level=RiskLevel.LOW,
        )

    @property
    def tool_spec(self) -> ToolSpec:
        return self._tool_spec

    async def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        query = arguments.get("query", "")
        if not query.strip():
            return {
                "message": "A consulta de busca não pode ser vazia.",
                "data": {"error": "empty_query"},
            }

        max_results = arguments.get("max_results", self._max_results)
        timelimit = arguments.get("timelimit")

        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return {
                "message": "Biblioteca duckduckgo-search não está instalada.",
                "data": {"error": "missing_dependency"},
            }

        def _search() -> list[dict[str, str]]:
            with DDGS(timeout=self._timeout) as ddgs:
                return ddgs.text(
                    keywords=query,
                    region=self._region,
                    safesearch=self._safesearch,
                    timelimit=timelimit,
                    max_results=max_results,
                )

        results = await asyncio.to_thread(_search)

        if not results:
            return {
                "message": f"Nenhum resultado encontrado para '{query}'.",
                "data": {"query": query, "results": []},
            }

        items = [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in results
        ]

        titles = "; ".join(r["title"] for r in items[:3])
        message = f"Encontrei {len(items)} resultados para '{query}'. Destaques: {titles}."

        return {
            "message": message,
            "data": {"query": query, "result_count": len(items), "results": items},
        }


class DuckDuckGoNewsTool(IToolProvider):
    """News search tool backed by the duckduckgo-search library."""

    def __init__(
        self,
        *,
        max_results: int = 5,
        region: str = "wt-wt",
        safesearch: str = "moderate",
        timeout: int = 10,
    ) -> None:
        self._max_results = max_results
        self._region = region
        self._safesearch = safesearch
        self._timeout = timeout
        self._tool_spec = ToolSpec(
            id="news_search",
            name="news_search",
            description=(
                "Search recent news using DuckDuckGo. "
                "Returns headlines, sources and URLs."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The news search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5).",
                    },
                    "timelimit": {
                        "type": "string",
                        "description": "Time filter: 'd' (past day), 'w' (past week), 'm' (past month).",
                        "enum": ["d", "w", "m"],
                    },
                },
                "required": ["query"],
            },
            output_schema={"type": "object"},
            risk_level=RiskLevel.LOW,
        )

    @property
    def tool_spec(self) -> ToolSpec:
        return self._tool_spec

    async def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> dict[str, Any]:
        query = arguments.get("query", "")
        if not query.strip():
            return {
                "message": "A consulta de busca não pode ser vazia.",
                "data": {"error": "empty_query"},
            }

        max_results = arguments.get("max_results", self._max_results)
        timelimit = arguments.get("timelimit")

        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return {
                "message": "Biblioteca duckduckgo-search não está instalada.",
                "data": {"error": "missing_dependency"},
            }

        def _search() -> list[dict[str, str]]:
            with DDGS(timeout=self._timeout) as ddgs:
                return ddgs.news(
                    keywords=query,
                    region=self._region,
                    safesearch=self._safesearch,
                    timelimit=timelimit,
                    max_results=max_results,
                )

        results = await asyncio.to_thread(_search)

        if not results:
            return {
                "message": f"Nenhuma notícia encontrada para '{query}'.",
                "data": {"query": query, "results": []},
            }

        items = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("body", ""),
                "source": r.get("source", ""),
                "date": r.get("date", ""),
            }
            for r in results
        ]

        titles = "; ".join(r["title"] for r in items[:3])
        message = f"Encontrei {len(items)} notícias para '{query}'. Destaques: {titles}."

        return {
            "message": message,
            "data": {"query": query, "result_count": len(items), "results": items},
        }
