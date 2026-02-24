from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class TestBuildRuntime(unittest.TestCase):

    def _env(self, **kwargs):
        """Helper to build a minimal env dict."""
        base = {
            "OPENAI_API_KEY": "sk-test",
            "GUARA_LLM": "openai",
            "GUARA_STT": "whisper",
            "GUARA_TTS": "piper",
            "PIPER_MODEL_PATH": "/fake/model.onnx",
        }
        base.update(kwargs)
        return base

    @patch("adapters.tts_piper.PiperVoice")
    @patch("adapters.stt_whisper.WhisperModel")
    @patch("adapters.llm_openai.AsyncOpenAI")
    def test_build_runtime_returns_guara_runtime(self, MockOpenAI, MockWhisper, MockPiper):
        from runtime.app import GuaraRuntime
        from runtime.config import build_runtime

        MockPiper.load.return_value = MagicMock()

        with patch.dict(os.environ, self._env()):
            runtime = build_runtime()

        assert isinstance(runtime, GuaraRuntime)

    @patch("adapters.tts_piper.PiperVoice")
    @patch("adapters.stt_whisper.WhisperModel")
    @patch("adapters.llm_openai.AsyncOpenAI")
    def test_active_providers_match_env(self, MockOpenAI, MockWhisper, MockPiper):
        from adapters.llm_openai import OpenAILLMProvider
        from adapters.stt_whisper import WhisperSTTProvider
        from adapters.tts_piper import PiperTTSProvider
        from runtime.config import build_runtime

        MockPiper.load.return_value = MagicMock()

        with patch.dict(os.environ, self._env()):
            runtime = build_runtime()

        assert isinstance(runtime.llm_provider, OpenAILLMProvider)
        assert isinstance(runtime.stt_provider, WhisperSTTProvider)
        assert isinstance(runtime.tts_provider, PiperTTSProvider)

    def test_missing_openai_key_raises(self):
        from runtime.config import build_runtime

        with patch.dict(os.environ, {"GUARA_LLM": "openai"}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                build_runtime()
        assert "OPENAI_API_KEY" in str(ctx.exception)

    @patch("adapters.tts_piper.PiperVoice")
    @patch("adapters.stt_whisper.WhisperModel")
    @patch("adapters.llm_openai.AsyncOpenAI")
    def test_deepgram_registered_when_key_present(self, MockOpenAI, MockWhisper, MockPiper):
        from adapters.stt_deepgram import DeepgramSTTProvider
        from runtime.config import build_runtime

        MockPiper.load.return_value = MagicMock()

        env = self._env(DEEPGRAM_API_KEY="dg-test", GUARA_STT="deepgram")
        with patch("adapters.stt_deepgram.DeepgramClient"), patch.dict(os.environ, env):
            runtime = build_runtime()

        assert isinstance(runtime.stt_provider, DeepgramSTTProvider)
