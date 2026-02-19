from __future__ import annotations

import unittest

from core.streaming import split_text_for_streaming


class TestStreamingUtils(unittest.TestCase):
    def test_split_text_for_streaming_sentence_aware(self) -> None:
        text = "Primeira frase curta. Segunda frase um pouco maior! Terceira?"
        chunks = split_text_for_streaming(text, max_chunk_chars=24)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk.strip() for chunk in chunks))

    def test_split_text_for_streaming_empty(self) -> None:
        self.assertEqual(split_text_for_streaming("   "), [])

