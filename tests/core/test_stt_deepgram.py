from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestDeepgramSTTProvider(unittest.IsolatedAsyncioTestCase):

    def _make_mock_client(self, transcript: str = "texto transcrito"):
        """Mock DeepgramClient that returns a fixed transcript."""
        mock_alt = MagicMock()
        mock_alt.transcript = transcript

        mock_channel = MagicMock()
        mock_channel.alternatives = [mock_alt]

        mock_results = MagicMock()
        mock_results.channels = [mock_channel]

        mock_response = MagicMock()
        mock_response.results = mock_results

        mock_prerecorded = MagicMock()
        mock_prerecorded.transcribe_file.return_value = mock_response

        mock_listen = MagicMock()
        mock_listen.prerecorded.v.return_value = mock_prerecorded

        mock_client = MagicMock()
        mock_client.listen = mock_listen
        return mock_client

    @patch("adapters.stt_deepgram.DeepgramClient")
    async def test_transcribe_returns_text(self, MockClient):
        from adapters.stt_deepgram import DeepgramSTTProvider

        MockClient.return_value = self._make_mock_client("texto transcrito")
        provider = DeepgramSTTProvider(api_key="dg-test")

        result = await provider.transcribe(b"fake audio")

        assert result == "texto transcrito"

    @patch("adapters.stt_deepgram.DeepgramClient")
    async def test_transcribe_stream_emits_final_chunk(self, MockClient):
        from adapters.stt_deepgram import DeepgramSTTProvider

        MockClient.return_value = self._make_mock_client("resultado")
        provider = DeepgramSTTProvider(api_key="dg-test")

        async def _audio_stream():
            yield b"fake audio"

        chunks = [c async for c in provider.transcribe_stream(_audio_stream())]

        assert len(chunks) == 1
        assert chunks[0].text == "resultado"
        assert chunks[0].is_final is True

    @patch("adapters.stt_deepgram.DeepgramClient")
    async def test_uses_language_override(self, MockClient):
        from adapters.stt_deepgram import DeepgramSTTProvider

        mock_client = self._make_mock_client("ok")
        MockClient.return_value = mock_client
        provider = DeepgramSTTProvider(api_key="dg-test", language="en-US")

        await provider.transcribe(b"audio", language="en-US")

        call_args = mock_client.listen.prerecorded.v.return_value.transcribe_file.call_args
        options = call_args[0][1]
        assert options.language == "en-US"
