from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestWhisperSTTProvider(unittest.IsolatedAsyncioTestCase):

    def _make_mock_model(self, text: str = "olá mundo"):
        """Mock WhisperModel that returns a fixed transcription."""
        mock_segment = MagicMock()
        mock_segment.text = text

        mock_info = MagicMock()

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        return mock_model

    @patch("adapters.stt_whisper.WhisperModel")
    async def test_transcribe_returns_text(self, MockModel):
        from adapters.stt_whisper import WhisperSTTProvider

        MockModel.return_value = self._make_mock_model("olá mundo")
        provider = WhisperSTTProvider(model_size="base")

        result = await provider.transcribe(b"fake audio")

        assert result == "olá mundo"

    @patch("adapters.stt_whisper.WhisperModel")
    async def test_transcribe_stream_emits_final_chunk(self, MockModel):
        from adapters.stt_whisper import WhisperSTTProvider

        MockModel.return_value = self._make_mock_model("transcrição")
        provider = WhisperSTTProvider(model_size="base")

        async def _audio_stream():
            yield b"fake audio"

        chunks = [c async for c in provider.transcribe_stream(_audio_stream())]

        assert len(chunks) == 1
        assert chunks[0].text == "transcrição"
        assert chunks[0].is_final is True

    @patch("adapters.stt_whisper.WhisperModel")
    async def test_transcribe_joins_multiple_segments(self, MockModel):
        from adapters.stt_whisper import WhisperSTTProvider

        seg1, seg2 = MagicMock(), MagicMock()
        seg1.text = "primeira"
        seg2.text = "segunda"
        MockModel.return_value.transcribe.return_value = ([seg1, seg2], MagicMock())

        provider = WhisperSTTProvider(model_size="base")
        result = await provider.transcribe(b"audio")

        assert "primeira" in result
        assert "segunda" in result

    @patch("adapters.stt_whisper.WhisperModel")
    async def test_uses_configured_model_size(self, MockModel):
        from adapters.stt_whisper import WhisperSTTProvider

        WhisperSTTProvider(model_size="large-v3")

        MockModel.assert_called_once_with("large-v3", device="cpu", compute_type="int8")
