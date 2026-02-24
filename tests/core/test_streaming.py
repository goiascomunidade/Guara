from __future__ import annotations

import unittest

from core.streaming import sentence_buffer, split_text_for_streaming


async def _token_stream(*tokens: str):
    for t in tokens:
        yield t


class TestSentenceBuffer(unittest.IsolatedAsyncioTestCase):
    async def test_yields_complete_sentences(self) -> None:
        tokens = ["Olá", ",", " eu", " posso", " ajudar", ".", " Como", " vai", "?"]
        sentences = [s async for s in sentence_buffer(_token_stream(*tokens))]
        self.assertEqual(len(sentences), 2)
        self.assertIn("ajudar", sentences[0])
        self.assertIn("vai", sentences[1])

    async def test_yields_remainder_without_punctuation(self) -> None:
        tokens = ["sem", " ponto", " final"]
        sentences = [s async for s in sentence_buffer(_token_stream(*tokens))]
        self.assertEqual(len(sentences), 1)
        self.assertIn("final", sentences[0])

    async def test_empty_stream_yields_nothing(self) -> None:
        sentences = [s async for s in sentence_buffer(_token_stream())]
        self.assertEqual(sentences, [])


class TestStreamingUtils(unittest.TestCase):
    def test_split_text_for_streaming_sentence_aware(self) -> None:
        text = "Primeira frase curta. Segunda frase um pouco maior! Terceira?"
        chunks = split_text_for_streaming(text, max_chunk_chars=24)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk.strip() for chunk in chunks))

    def test_split_text_for_streaming_empty(self) -> None:
        self.assertEqual(split_text_for_streaming("   "), [])

