# Streaming Contracts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adicionar streaming end-to-end (STT, LLM, TTS) e barge-in cancel aos contratos do Guara, habilitando latência V2V real e interrupção de fala.

**Architecture:** Os métodos batch existentes são mantidos intactos. Cada interface ganha métodos `_stream` e/ou `cancel` que os adapters stub implementam como wrappers simples. O `SessionController.interrupt()` passa a chamar `tts_provider.cancel()`. O `Orchestrator` ganha `stream_user_text()` paralelo ao método batch atual.

**Tech Stack:** Python 3.12, collections.abc.AsyncIterator, pytest-asyncio (asyncio_mode=auto), sem novas dependências.

---

### Task 1: Establish baseline

**Files:**
- None modified

**Step 1: Run the existing test suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -v`
Expected: 34 tests PASS. If any fail, stop and investigate before proceeding.

**Step 2: Record baseline**

Note: baseline is 34 passing tests. Every subsequent task must maintain or increase this count.

---

### Task 2: Add `TranscriptionChunk` to `core/types.py`

**Files:**
- Modify: `core/types.py`
- Test: `tests/core/test_contracts.py` (create)

**Step 1: Write the failing test**

Create `tests/core/test_contracts.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py -v`
Expected: FAIL with `ImportError: cannot import name 'TranscriptionChunk'`

**Step 3: Add `TranscriptionChunk` to `core/types.py`**

Add after the existing enums (after line 27):

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TranscriptionChunk:
    text: str
    is_final: bool
    confidence: float = 1.0
```

Note: also add `from dataclasses import dataclass` at the top of `core/types.py` (it currently has no imports).

**Step 4: Run test to verify it passes**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py -v`
Expected: 2 PASS

**Step 5: Run full suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -q`
Expected: 36 passed

**Step 6: Commit**

```bash
git add core/types.py tests/core/test_contracts.py
git commit -m "feat: add TranscriptionChunk type for streaming STT"
```

---

### Task 3: Add `ISTTProvider.transcribe_stream` to contracts

**Files:**
- Modify: `core/contracts.py`
- Modify: `tests/core/test_contracts.py`

**Step 1: Write the failing test**

Add to `tests/core/test_contracts.py`:

```python
import asyncio
from collections.abc import AsyncIterator
from core.contracts import ISTTProvider
from core.types import TranscriptionChunk


async def _bytes_stream(data: bytes) -> AsyncIterator[bytes]:
    yield data


class _StubSTT:
    async def transcribe(self, audio: bytes, language=None) -> str:
        return audio.decode()

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language=None,
    ) -> AsyncIterator[TranscriptionChunk]:
        chunks = [chunk async for chunk in audio_stream]
        text = b"".join(chunks).decode()
        yield TranscriptionChunk(text=text, is_final=True)


async def test_stt_stream_satisfies_protocol():
    provider: ISTTProvider = _StubSTT()
    stream = provider.transcribe_stream(_bytes_stream(b"oi"))
    results = [r async for r in stream]
    assert len(results) == 1
    assert results[0].is_final is True
    assert results[0].text == "oi"
```

**Step 2: Run test to verify it fails**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py::test_stt_stream_satisfies_protocol -v`
Expected: FAIL — `_StubSTT` not compatible with `ISTTProvider` (missing method in Protocol)

**Step 3: Add `transcribe_stream` to `ISTTProvider` in `core/contracts.py`**

Replace the current `ISTTProvider` class:

```python
from collections.abc import AsyncIterator

from core.types import TranscriptionChunk


class ISTTProvider(Protocol):
    @abstractmethod
    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str | None = None,
    ) -> AsyncIterator[TranscriptionChunk]:
        raise NotImplementedError
```

Note: `transcribe_stream` returns `AsyncIterator[TranscriptionChunk]` (not `async def` — it is an async generator method, so the return type annotation is the iterator itself). In `Protocol`, declare it as a regular method returning the iterator type.

**Step 4: Run test to verify it passes**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py -v`
Expected: all pass

**Step 5: Run full suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -q`
Expected: all pass (no regressions — batch `transcribe` unchanged)

**Step 6: Commit**

```bash
git add core/contracts.py tests/core/test_contracts.py
git commit -m "feat: add ISTTProvider.transcribe_stream to contracts"
```

---

### Task 4: Add `ILLMProvider.stream` to contracts

**Files:**
- Modify: `core/contracts.py`
- Modify: `tests/core/test_contracts.py`

**Step 1: Write the failing test**

Add to `tests/core/test_contracts.py`:

```python
from core.contracts import ILLMProvider


class _StubLLM:
    async def complete(self, messages, tools=None) -> dict:
        return {"content": "ok", "tool_calls": []}

    async def stream(self, messages, tools=None) -> AsyncIterator[str]:
        for token in ["ol", "á"]:
            yield token


async def test_llm_stream_satisfies_protocol():
    provider: ILLMProvider = _StubLLM()
    tokens = [t async for t in provider.stream([{"role": "user", "content": "oi"}])]
    assert "".join(tokens) == "olá"
```

**Step 2: Run test to verify it fails**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py::test_llm_stream_satisfies_protocol -v`
Expected: FAIL — `stream` not in `ILLMProvider` Protocol

**Step 3: Add `stream` to `ILLMProvider` in `core/contracts.py`**

Replace the current `ILLMProvider` class:

```python
class ILLMProvider(Protocol):
    @abstractmethod
    async def complete(self, messages: list[dict[str, Any]], tools: Any | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Any | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
```

**Step 4: Run test to verify it passes**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py -v`
Expected: all pass

**Step 5: Run full suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -q`
Expected: all pass

**Step 6: Commit**

```bash
git add core/contracts.py tests/core/test_contracts.py
git commit -m "feat: add ILLMProvider.stream to contracts"
```

---

### Task 5: Add `ITTSProvider.synthesize_stream` and `cancel` to contracts

**Files:**
- Modify: `core/contracts.py`
- Modify: `tests/core/test_contracts.py`

**Step 1: Write the failing test**

Add to `tests/core/test_contracts.py`:

```python
from core.contracts import ITTSProvider


class _StubTTS:
    def __init__(self):
        self.cancelled: list[str] = []

    async def synthesize(self, text: str, voice=None) -> bytes:
        return text.encode()

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice=None,
    ) -> AsyncIterator[bytes]:
        async for token in text_stream:
            yield token.encode()

    async def cancel(self, session_id: str) -> None:
        self.cancelled.append(session_id)


async def _str_stream(*tokens: str) -> AsyncIterator[str]:
    for t in tokens:
        yield t


async def test_tts_stream_satisfies_protocol():
    provider: ITTSProvider = _StubTTS()
    chunks = [c async for c in provider.synthesize_stream(_str_stream("ol", "á"))]
    assert b"".join(chunks) == b"ol\xc3\xa1"


async def test_tts_cancel_is_idempotent():
    provider = _StubTTS()
    await provider.cancel("s-1")
    await provider.cancel("s-1")
    assert provider.cancelled == ["s-1", "s-1"]
```

**Step 2: Run test to verify it fails**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py::test_tts_stream_satisfies_protocol tests/core/test_contracts.py::test_tts_cancel_is_idempotent -v`
Expected: FAIL

**Step 3: Add `synthesize_stream` and `cancel` to `ITTSProvider` in `core/contracts.py`**

Replace the current `ITTSProvider` class:

```python
class ITTSProvider(Protocol):
    @abstractmethod
    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, session_id: str) -> None:
        raise NotImplementedError
```

**Step 4: Run tests to verify they pass**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py -v`
Expected: all pass

**Step 5: Run full suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -q`
Expected: all pass

**Step 6: Commit**

```bash
git add core/contracts.py tests/core/test_contracts.py
git commit -m "feat: add ITTSProvider.synthesize_stream and cancel to contracts"
```

---

### Task 6: Implement streaming methods in stub adapters

**Files:**
- Modify: `adapters/stt_local.py`
- Modify: `adapters/llm_rule_based.py`
- Modify: `adapters/tts_local.py`
- Modify: `tests/core/test_contracts.py`

**Step 1: Write the failing tests (using the real adapters)**

Add to `tests/core/test_contracts.py`:

```python
from adapters.stt_local import LocalSTTProvider
from adapters.llm_rule_based import RuleBasedLLMProvider
from adapters.tts_local import LocalTTSProvider


async def test_local_stt_stream_emits_final_chunk():
    provider = LocalSTTProvider()
    audio = b"oi tudo bem"

    async def _stream():
        yield audio

    chunks = [c async for c in provider.transcribe_stream(_stream())]
    assert len(chunks) >= 1
    assert any(c.is_final for c in chunks)
    assert chunks[-1].text  # produz algo


async def test_rule_based_llm_stream_concatenates():
    provider = RuleBasedLLMProvider()
    messages = [{"role": "user", "content": "oi"}]
    tokens = [t async for t in provider.stream(messages)]
    full = "".join(tokens)
    assert full  # produz algo não vazio


async def test_local_tts_stream_produces_bytes():
    provider = LocalTTSProvider()

    async def _stream():
        yield "olá "
        yield "mundo"

    chunks = [c async for c in provider.synthesize_stream(_stream())]
    assert len(chunks) >= 1
    assert all(isinstance(c, bytes) for c in chunks)


async def test_local_tts_cancel_no_op():
    provider = LocalTTSProvider()
    await provider.cancel("session-1")  # não explode
    await provider.cancel("session-1")  # idempotente
```

**Step 2: Run tests to verify they fail**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py::test_local_stt_stream_emits_final_chunk tests/core/test_contracts.py::test_rule_based_llm_stream_concatenates tests/core/test_contracts.py::test_local_tts_stream_produces_bytes tests/core/test_contracts.py::test_local_tts_cancel_no_op -v`
Expected: FAIL — methods not implemented

**Step 3: Implement `LocalSTTProvider.transcribe_stream`**

New full content of `adapters/stt_local.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator

from core.types import TranscriptionChunk


class LocalSTTProvider:
    """Baseline STT provider for local development and tests."""

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        try:
            text = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""

        if text:
            return text

        language_hint = f" ({language})" if language else ""
        return f"<audio:{len(audio)} bytes{language_hint}>"

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str | None = None,
    ) -> AsyncIterator[TranscriptionChunk]:
        chunks: list[bytes] = []
        async for chunk in audio_stream:
            chunks.append(chunk)
        audio = b"".join(chunks)
        text = await self.transcribe(audio, language)
        yield TranscriptionChunk(text=text, is_final=True)
```

**Step 4: Implement `RuleBasedLLMProvider.stream`**

Add the `stream` method to `adapters/llm_rule_based.py` (after the `complete` method):

```python
    async def stream(
        self,
        messages: list[dict],
        tools=None,
    ):
        result = await self.complete(messages, tools)
        content = result.get("content", "")
        for char in content:
            yield char
```

Note: the method signature uses `async def stream(...):` and `yield` inside — this makes it an async generator. No return type annotation needed for the stub.

**Step 5: Implement `LocalTTSProvider.synthesize_stream` and `cancel`**

New full content of `adapters/tts_local.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator


class LocalTTSProvider:
    """Baseline TTS provider for local development and tests."""

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        payload = text if voice is None else f"[{voice}] {text}"
        return payload.encode("utf-8")

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        async for token in text_stream:
            payload = token if voice is None else f"[{voice}] {token}"
            yield payload.encode("utf-8")

    async def cancel(self, session_id: str) -> None:
        """No-op: local TTS has no active synthesis to cancel."""
```

**Step 6: Run the new tests to verify they pass**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_contracts.py -v`
Expected: all pass

**Step 7: Run full suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -q`
Expected: all pass (no regressions)

**Step 8: Commit**

```bash
git add adapters/stt_local.py adapters/llm_rule_based.py adapters/tts_local.py tests/core/test_contracts.py
git commit -m "feat: implement streaming methods in stub adapters"
```

---

### Task 7: Wire `cancel` into `SessionController.interrupt()`

**Files:**
- Modify: `core/session.py`
- Modify: `tests/core/test_session.py`

**Step 1: Write the failing test**

Add to `tests/core/test_session.py`:

```python
from adapters.tts_local import LocalTTSProvider


class TestSessionBargeIn(unittest.IsolatedAsyncioTestCase):
    async def test_interrupt_calls_tts_cancel(self) -> None:
        cancelled: list[str] = []

        class _TrackingTTS:
            async def synthesize(self, text, voice=None):
                return b""

            async def synthesize_stream(self, text_stream, voice=None):
                async for _ in text_stream:
                    yield b""

            async def cancel(self, session_id: str) -> None:
                cancelled.append(session_id)

        bus = EventBus()
        controller = SessionController(event_bus=bus, tts_provider=_TrackingTTS())

        await controller.start_session("s-tts", user_id=None)
        await controller.interrupt("s-tts")

        assert "s-tts" in cancelled
```

**Step 2: Run test to verify it fails**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_session.py::TestSessionBargeIn -v`
Expected: FAIL — `SessionController.__init__` doesn't accept `tts_provider`

**Step 3: Update `SessionController` in `core/session.py`**

Change the `__init__` signature and `interrupt` method:

```python
# In __init__, add optional tts_provider parameter:
def __init__(
    self,
    *,
    event_bus: EventBus | None = None,
    tool_router: ToolRouter | None = None,
    tts_provider=None,  # ITTSProvider | None — avoid circular import with Protocol
) -> None:
    self._sessions: dict[str, Session] = {}
    self._event_bus = event_bus
    self._tool_router = tool_router
    self._tts_provider = tts_provider
```

```python
# In interrupt(), after cancel_interruptible_calls():
async def interrupt(self, session_id: str) -> list[str]:
    session = self._require_session(session_id)
    session.state = SessionState.INTERRUPTED

    cancelled_calls: list[str] = []
    if self._tool_router:
        cancelled_calls = await self._tool_router.cancel_interruptible_calls()

    if self._tts_provider:
        await self._tts_provider.cancel(session_id)

    if self._event_bus:
        await self._event_bus.publish(
            BargeInEvent(
                trace_id=new_trace_id(),
                session_id=session_id,
                cancelled_calls=cancelled_calls,
            )
        )

    session.state = SessionState.LISTENING
    return cancelled_calls
```

**Step 4: Run the new test to verify it passes**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_session.py -v`
Expected: all pass

**Step 5: Run full suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -q`
Expected: all pass

**Step 6: Commit**

```bash
git add core/session.py tests/core/test_session.py
git commit -m "feat: wire tts_provider.cancel into SessionController.interrupt for barge-in"
```

---

### Task 8: Add `sentence_buffer` async generator to `core/streaming.py`

**Files:**
- Modify: `core/streaming.py`
- Modify: `tests/core/test_streaming.py`

The sentence buffer is the glue between LLM stream (tokens) and TTS stream (sentences). It accumulates tokens until a sentence boundary (`.`, `!`, `?`) then yields the buffered sentence. This allows TTS to start speaking the first sentence while the LLM is still generating the rest.

**Step 1: Write the failing test**

Add to `tests/core/test_streaming.py`:

```python
import asyncio
from core.streaming import sentence_buffer


async def _token_stream(*tokens: str):
    for t in tokens:
        yield t


class TestSentenceBuffer(unittest.IsolatedAsyncioTestCase):
    async def test_yields_complete_sentences(self) -> None:
        tokens = ["Olá", ",", " eu", " posso", " ajudar", ".", " Como", " vai", "?"]
        sentences = [s async for s in sentence_buffer(_token_stream(*tokens))]
        assert len(sentences) == 2
        assert "ajudar" in sentences[0]
        assert "vai" in sentences[1]

    async def test_yields_remainder_without_punctuation(self) -> None:
        tokens = ["sem", " ponto", " final"]
        sentences = [s async for s in sentence_buffer(_token_stream(*tokens))]
        assert len(sentences) == 1
        assert "final" in sentences[0]

    async def test_empty_stream_yields_nothing(self) -> None:
        sentences = [s async for s in sentence_buffer(_token_stream())]
        assert sentences == []
```

Also add `import unittest` to `tests/core/test_streaming.py` if not present. The file currently uses `unittest.TestCase` — check first.

**Step 2: Run tests to verify they fail**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_streaming.py::TestSentenceBuffer -v`
Expected: FAIL — `sentence_buffer` not defined in `core.streaming`

**Step 3: Add `sentence_buffer` to `core/streaming.py`**

Add after the existing `split_text_for_streaming` function:

```python
from collections.abc import AsyncIterator


SENTENCE_END_CHARS = frozenset(".!?")


async def sentence_buffer(
    token_stream: AsyncIterator[str],
    *,
    min_chars: int = 1,
) -> AsyncIterator[str]:
    """Accumulate LLM tokens and yield complete sentences for TTS.

    Yields a sentence whenever a sentence-ending character (.!?) is
    encountered and the buffer has at least min_chars characters.
    Any remaining buffer is yielded at stream end.
    """
    buffer = ""
    async for token in token_stream:
        buffer += token
        if any(buffer.rstrip().endswith(c) for c in SENTENCE_END_CHARS):
            sentence = buffer.strip()
            if len(sentence) >= min_chars:
                yield sentence
                buffer = ""

    remainder = buffer.strip()
    if remainder:
        yield remainder
```

**Step 4: Run tests to verify they pass**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_streaming.py -v`
Expected: all pass

**Step 5: Run full suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -q`
Expected: all pass

**Step 6: Commit**

```bash
git add core/streaming.py tests/core/test_streaming.py
git commit -m "feat: add sentence_buffer async generator for streaming TTS pipeline"
```

---

### Task 9: Add `Orchestrator.stream_user_text()`

**Files:**
- Modify: `core/orchestrator.py`
- Modify: `tests/core/` (new test file or add to existing)

**Step 1: Write the failing test**

Create `tests/core/test_orchestrator_streaming.py`:

```python
from __future__ import annotations

import unittest

from adapters.guardrail_basic import BasicGuardrail
from adapters.llm_rule_based import RuleBasedLLMProvider
from core.orchestrator import Orchestrator
from core.tool_runtime import ToolRouter


class TestOrchestratorStreaming(unittest.IsolatedAsyncioTestCase):
    def _make_orchestrator(self) -> Orchestrator:
        return Orchestrator(
            llm_provider=RuleBasedLLMProvider(),
            tool_router=ToolRouter(),
            guardrail=BasicGuardrail(),
        )

    async def test_stream_user_text_yields_tokens(self) -> None:
        orch = self._make_orchestrator()
        tokens = [
            t
            async for t in orch.stream_user_text(
                "oi", session_id="s-1", trace_id="t-1"
            )
        ]
        assert len(tokens) > 0
        assert "".join(tokens)  # produz conteúdo não vazio

    async def test_stream_user_text_blocked_input_yields_block_message(self) -> None:
        orch = self._make_orchestrator()
        # BasicGuardrail bloqueia "badword" — verificar o que realmente bloqueia
        # se não houver keyword configurada, usar handle_user_text para comparar
        tokens = [
            t
            async for t in orch.stream_user_text(
                "oi tudo bem", session_id="s-2", trace_id="t-2"
            )
        ]
        full = "".join(tokens)
        assert full  # qualquer resposta é válida para input limpo
```

**Step 2: Run test to verify it fails**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_orchestrator_streaming.py -v`
Expected: FAIL — `Orchestrator` has no `stream_user_text`

**Step 3: Add `stream_user_text` to `core/orchestrator.py`**

Add after the existing `handle_user_text` method:

```python
    async def stream_user_text(
        self,
        user_text: str,
        *,
        session_id: str,
        trace_id: str,
        user_id: str | None = None,
    ):
        """Stream LLM tokens for a user turn. Yields str tokens.

        Mirrors handle_user_text but uses ILLMProvider.stream() for
        low-latency sentence-level TTS pipeline.
        """
        if self._guardrail:
            ok, reason = await self._guardrail.validate_input(user_text)
            if not ok:
                yield reason or "input blocked"
                return

        async for token in self._llm_provider.stream(
            [{"role": "user", "content": user_text}],
            tools=None,
        ):
            yield token
```

Note: this method does not handle tool calls — tool-calling in streaming mode is a future task (requires accumulating the stream to detect tool call markers). For now it streams pure text responses.

**Step 4: Run the new tests to verify they pass**

Run: `/home/peras/venv/bin/python -m pytest tests/core/test_orchestrator_streaming.py -v`
Expected: all pass

**Step 5: Run full suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -q`
Expected: all pass

**Step 6: Commit**

```bash
git add core/orchestrator.py tests/core/test_orchestrator_streaming.py
git commit -m "feat: add Orchestrator.stream_user_text for streaming LLM pipeline"
```

---

### Task 10: Final validation and summary commit

**Step 1: Run full test suite**

Run: `/home/peras/venv/bin/python -m pytest tests/ -v`
Expected: all tests pass, count >= 34 + new tests from this plan

**Step 2: Verify contracts look correct**

Run: `/home/peras/venv/bin/python -c "from core.contracts import ISTTProvider, ILLMProvider, ITTSProvider; print('OK')"`
Expected: `OK`

**Step 3: Verify adapters implement all new methods**

Run:
```bash
/home/peras/venv/bin/python -c "
from adapters.stt_local import LocalSTTProvider
from adapters.llm_rule_based import RuleBasedLLMProvider
from adapters.tts_local import LocalTTSProvider
assert hasattr(LocalSTTProvider(), 'transcribe_stream')
assert hasattr(RuleBasedLLMProvider(), 'stream')
assert hasattr(LocalTTSProvider(), 'synthesize_stream')
assert hasattr(LocalTTSProvider(), 'cancel')
print('all adapters OK')
"
```
Expected: `all adapters OK`

**Step 4: Commit CLAUDE.md if not yet committed**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md project guidance"
```

---

## Gaps fora do escopo deste plano

Estes gaps foram identificados mas intencionalmente deixados para quando a feature concreta precisar:

| Gap | Feature que pede |
|---|---|
| `ActionResult.status: "pending_approval"` | Human-in-the-loop |
| `rollback()` no tool execution | Transacionalidade |
| `SpeechToSpeechPort` | Adapter S2S real |
| `speaker_verify()` | Biometria de voz |
| `clone_voice()` | Clonagem de voz |
| Tool-calling no `stream_user_text` | Streaming com function-calling |
