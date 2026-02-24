from __future__ import annotations

import unittest

from core.summarizer import ContextSummarizer, SummarizationConfig


class TestSummarizer(unittest.IsolatedAsyncioTestCase):
    async def test_context_summarizer_threshold_and_result_shape(self) -> None:
        summarizer = ContextSummarizer(
            SummarizationConfig(
                max_context_tokens=10,
                max_unsummarized_messages=4,
                min_messages_to_keep=2,
                target_context_tokens=120,
            )
        )
        messages = [
            {"role": "user", "content": "Oi"},
            {"role": "assistant", "content": "Oi! Como posso ajudar?"},
            {"role": "user", "content": "Quero planejar uma viagem para semana que vem."},
            {"role": "assistant", "content": "Perfeito, qual destino?"},
            {"role": "user", "content": "Lisboa."},
        ]

        self.assertTrue(summarizer.should_summarize(messages))
        result = await summarizer.summarize(messages)

        self.assertIsNone(result.error)
        self.assertTrue(result.summary)
        self.assertGreaterEqual(result.last_summarized_index, 0)
