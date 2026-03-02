from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class TestBuildListener(unittest.TestCase):

    def test_build_listener_reads_env_vars(self):
        from runtime.listener_main import build_listener

        fake_runtime = MagicMock()
        env = {
            "PORCUPINE_ACCESS_KEY": "my-key",
            "PORCUPINE_KEYWORD_PATH": "/tmp/guara.ppn",
            "PORCUPINE_SENSITIVITY": "0.7",
            "PORCUPINE_DEVICE_INDEX": "2",
            "GUARA_WAKE_WORD": "assistente",
            "GUARA_STOP_WORD": "pronto",
        }
        with patch.dict(os.environ, env):
            listener = build_listener(fake_runtime)

        assert listener.wake_word == "assistente"
        assert listener.stop_word == "pronto"
        assert listener._porcupine_config.access_key == "my-key"
        assert listener._porcupine_config.keyword_path == "/tmp/guara.ppn"
        assert listener._porcupine_config.sensitivity == 0.7
        assert listener._porcupine_config.audio_device_index == 2

    def test_build_listener_uses_defaults(self):
        from runtime.listener_main import build_listener

        fake_runtime = MagicMock()
        for key in (
            "GUARA_WAKE_WORD", "GUARA_STOP_WORD",
            "PORCUPINE_ACCESS_KEY", "PORCUPINE_KEYWORD_PATH",
            "PORCUPINE_MODEL_PATH", "PORCUPINE_SENSITIVITY", "PORCUPINE_DEVICE_INDEX",
        ):
            os.environ.pop(key, None)

        listener = build_listener(fake_runtime)

        assert listener.wake_word == "guará"
        assert listener.stop_word == "obrigado"
        assert listener._porcupine_config.sensitivity == 0.5
        assert listener._porcupine_config.audio_device_index == -1
