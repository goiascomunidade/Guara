from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class TestBuildListener(unittest.TestCase):

    def test_build_listener_reads_env_vars(self):
        from runtime.listener_main import build_listener

        fake_runtime = MagicMock()
        env = {
            "GUARA_WAKE_WORD": "assistente",
            "GUARA_STOP_WORD": "pronto",
            "GUARA_VAD_THRESHOLD": "0.7",
        }
        with patch.dict(os.environ, env):
            listener = build_listener(fake_runtime)

        assert listener.wake_word == "assistente"
        assert listener.stop_word == "pronto"

    def test_build_listener_uses_defaults(self):
        from runtime.listener_main import build_listener

        fake_runtime = MagicMock()
        for key in ("GUARA_WAKE_WORD", "GUARA_STOP_WORD", "GUARA_VAD_THRESHOLD"):
            os.environ.pop(key, None)

        listener = build_listener(fake_runtime)

        assert listener.wake_word == "guará"
        assert listener.stop_word == "obrigado"
