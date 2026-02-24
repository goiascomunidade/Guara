from __future__ import annotations

from core.types import TranscriptionChunk


def test_transcription_chunk_defaults():
    chunk = TranscriptionChunk(text="olá", is_final=True)
    assert chunk.text == "olá"
    assert chunk.is_final is True
    assert chunk.confidence == 1.0


def test_transcription_chunk_partial():
    chunk = TranscriptionChunk(text="ol", is_final=False, confidence=0.7)
    assert chunk.is_final is False
    assert chunk.confidence == 0.7
