from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class TestOpenAILLMProvider(unittest.IsolatedAsyncioTestCase):

    def _make_mock_client(self, content: str = "olá!", tool_calls=None):
        """Build a mock AsyncOpenAI client that returns a fixed response."""
        mock_message = MagicMock()
        mock_message.content = content
        mock_message.tool_calls = tool_calls or []

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_completions = MagicMock()
        mock_completions.create = AsyncMock(return_value=mock_response)

        mock_chat = MagicMock()
        mock_chat.completions = mock_completions

        mock_client = MagicMock()
        mock_client.chat = mock_chat
        return mock_client

    @patch("adapters.llm_openai.AsyncOpenAI")
    async def test_complete_returns_content(self, MockClient):
        from adapters.llm_openai import OpenAILLMProvider

        MockClient.return_value = self._make_mock_client("olá!")
        provider = OpenAILLMProvider(api_key="sk-test", model="gpt-4o")

        result = await provider.complete([{"role": "user", "content": "oi"}])

        assert result["content"] == "olá!"
        assert result["tool_calls"] == []

    @patch("adapters.llm_openai.AsyncOpenAI")
    async def test_complete_with_tool_calls(self, MockClient):
        import json
        from adapters.llm_openai import OpenAILLMProvider

        mock_tc = MagicMock()
        mock_tc.id = "call-1"
        mock_tc.function.name = "get_weather"
        mock_tc.function.arguments = json.dumps({"city": "São Paulo"})

        MockClient.return_value = self._make_mock_client("", tool_calls=[mock_tc])
        provider = OpenAILLMProvider(api_key="sk-test")

        result = await provider.complete([{"role": "user", "content": "tempo em SP"}])

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "get_weather"
        assert result["tool_calls"][0]["arguments"] == {"city": "São Paulo"}

    @patch("adapters.llm_openai.AsyncOpenAI")
    async def test_stream_yields_tokens(self, MockClient):
        from adapters.llm_openai import OpenAILLMProvider

        async def _fake_stream():
            for char in ["ol", "á", "!"]:
                chunk = MagicMock()
                chunk.choices[0].delta.content = char
                yield chunk

        mock_create = MagicMock()
        mock_create.__aenter__ = AsyncMock(return_value=_fake_stream())
        mock_create.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_create
        MockClient.return_value = mock_client

        provider = OpenAILLMProvider(api_key="sk-test")
        tokens = [t async for t in provider.stream([{"role": "user", "content": "oi"}])]

        assert "".join(tokens) == "olá!"

    @patch("adapters.llm_openai.AsyncOpenAI")
    async def test_uses_configured_model(self, MockClient):
        from adapters.llm_openai import OpenAILLMProvider

        mock_client = self._make_mock_client("ok")
        MockClient.return_value = mock_client

        provider = OpenAILLMProvider(api_key="sk-test", model="gpt-5")
        await provider.complete([{"role": "user", "content": "oi"}])

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-5"
