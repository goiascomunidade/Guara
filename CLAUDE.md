# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python3 -m pytest

# Run a single test file
python3 -m pytest tests/core/test_session.py -v

# Run a single test by name
python3 -m pytest tests/core/test_tool_runtime.py::TestToolRuntime::test_tool_router_respects_parallel_limit -v

# Run the HTTP server
python3 -m runtime.main --host 0.0.0.0 --port 8080

# Run the WebSocket server
python3 -m transport.ws_main

# Install dev dependencies
pip install -e ".[dev]"
```

Async tests use `unittest.IsolatedAsyncioTestCase` — no `@pytest.mark.asyncio` needed.

## Architecture

Guara is a voice-to-voice agent runtime built around a hexagonal/ports-and-adapters design. The central idea: the `core/` package defines contracts (interfaces) and domain logic; `adapters/` implements those contracts; `runtime/` wires everything together.

### Core contracts (`core/contracts.py`)

Six `Protocol` interfaces define the pluggable extension points:
- `ISTTProvider` — speech-to-text (`transcribe(audio) -> str`, `transcribe_stream(audio_stream) -> AsyncIterator[TranscriptionChunk]`)
- `ITTSProvider` — text-to-speech (`synthesize(text) -> bytes`, `synthesize_stream(text_stream) -> AsyncIterator[bytes]`, `cancel(session_id)`)
- `ILLMProvider` — LLM completion (`complete(messages, tools) -> dict`, `stream(messages, tools) -> AsyncIterator[str]`)
- `IToolProvider` — a single executable tool (`tool_spec`, `execute(arguments, context)`)
- `IMemoryProvider` — key-value + RAG memory (`put/get/query`)
- `IGuardrail` — input/output content filtering

### Turn lifecycle

```
audio/text input
  → STT (if audio)
  → SessionController.push_audio_frame()   [emits TurnStartedEvent]
  → Orchestrator.handle_user_text()
      → IGuardrail.validate_input()
      → ILLMProvider.complete()
      → ToolRouter.execute_calls()          [parallel, dependency-aware, bounded]
      → IGuardrail.validate_output()
  → ITTSProvider.synthesize()
  → SessionController.complete_turn()      [emits TurnCompletedEvent]
```

The `GuaraRuntime` class in `runtime/app.py` is the composition root — it wires all the above together and exposes high-level methods (`start_session`, `process_text_turn`, `stream_text_turn_events`, etc.).

### Tool execution (`core/tool_runtime.py`)

`ToolRouter` handles:
- Bounded parallel execution via `asyncio.Semaphore(max_parallel_calls)`
- Dependency-aware scheduling via `ToolCall.depends_on` (wave-based topological execution)
- Per-tool `ToolPolicy` (timeout, cancel-on-interruption flag)
- Barge-in: `cancel_interruptible_calls()` cancels all cancellable in-flight tasks

### Events (`core/events.py`)

`EventBus` is a simple async pub/sub. All domain events are frozen dataclasses subclassing `TypedEvent` with `event_name` + `event_version`. `LocalEventStore` (`core/telemetry.py`) subscribes to all events and provides in-memory query.

### Session states (`core/types.py`)

`SessionState` enum: `IDLE → LISTENING → THINKING → SPEAKING → INTERRUPTED → ENDED / ERROR`

### Plugin SDK (`plugins/sdk.py`)

- `DirectFunctionToolProvider`: wraps a plain Python function as a tool; infers JSON schema from signature/docstring
- `PluginLoader`: discovers `plugin.json` manifests recursively, validates SemVer compatibility with core version
- `ToolManifest` (`core/manifest.py`): versioned manifest with `risk_level`, `autonomy_modes`, `compatibility` matrix

### Adapters (`adapters/`)

Stub/local implementations of all contracts:
- `LocalSTTProvider` — no-op transcription
- `LocalTTSProvider` — no-op synthesis (returns empty bytes)
- `RuleBasedLLMProvider` — keyword-based responses (for testing without a real LLM)
- `BasicGuardrail` — keyword-based content filtering
- `MCPHTTPClient` + `MCPToolProvider` — MCP tool discovery and execution over HTTP

### Transport layer (`transport/`)

- `runtime/http_server.py` — FastAPI/Starlette HTTP server with SSE streaming
- `transport/websocket_server.py` — WebSocket server
- `transport/realtime.py` — `RealtimeSessionManager` bridges WebSocket messages to `GuaraRuntime` stream generators
- `transport/ws_protocol.py` — `ClientMessage` wire format (`text_turn`, `audio_turn`, `interrupt`, `end`)

### Provider registry (`core/provider_registry.py`)

Named registry for STT/TTS/LLM providers; supports runtime switching via `switch(kind, name)`. Switch emits `ProviderSwitchedEvent`.

## Key design constraints

- **LLM has no secrets**: secrets stay in adapter/workflow layers, not passed to the LLM.
- **Tool contract**: tools return `{"message": str, "data": dict}` — `message` is speakable, `data` is for follow-up logic.
- **Post-tool default**: always run LLM after tool execution (`run_llm=True` on `ToolCall`).
- **Primary language**: Portuguese (English planned for a later phase).
