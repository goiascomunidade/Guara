# Guara

Guara is an open-source foundation for a voice-to-voice agent architecture.
This repository now includes the first implementation slice of the core runtime,
plugin contracts, and execution policies described in the system design plan.

## What is implemented

- Typed, versioned internal events (`core/events.py`)
- Session lifecycle controller (`core/session.py`)
- Orchestration entrypoint for LLM + tools (`core/orchestrator.py`)
- Universal tool schema and tool call contracts (`core/tools.py`)
- Tool runtime with:
  - bounded parallel execution
  - dependency-aware scheduling
  - per-tool timeout
  - interruption-aware cancellation (`core/tool_runtime.py`)
- Plugin manifest and compatibility validation (`core/manifest.py`)
- Plugin SDK for direct Python functions with inferred schema (`plugins/sdk.py`)
- Context summarization trigger logic (token/message thresholds) (`core/summarizer.py`)
- Local short-term memory store with TTL (`core/memory.py`)

## Repository structure

- `core/`: runtime contracts and orchestration primitives
- `adapters/`: provider-specific integration namespace
- `plugins/`: plugin SDK
- `runtime/`: application wiring and HTTP server
- `policies/`: default policy values
- `tests/`: behavioral tests for the architecture baseline
- `docs/architecture/`: architecture notes and decisions

## Quick start

1. Clone and install:

```bash
git clone https://github.com/peraro/Guara.git
cd Guara
pip install -e ".[all-providers]"
```

Or install only what you need:

```bash
pip install -e ".[openai,whisper,piper,wakeword]"
```

2. Copy and edit the env file:

```bash
cp .env.example .env
# edit .env with your API keys (OPENAI_API_KEY, PORCUPINE_ACCESS_KEY, etc.)
```

3. Run:

```bash
guara listen                # Wake-word listener (microphone)
guara serve                 # HTTP server (default: 0.0.0.0:8080)
guara serve --port 3000     # HTTP server on custom port
guara ws                    # WebSocket server (default: 0.0.0.0:8765)
```

## Development

Run tests:

```bash
pip install -e ".[dev]"
python3 -m pytest
```

Run HTTP runtime (without installing):

```bash
python3 -m runtime.main --host 0.0.0.0 --port 8080
```

Endpoints:
- `GET /health`
- `GET /tools`
- `GET /events?limit=100&event_name=...&session_id=...`
- `GET /providers`
- `POST /sessions/start`
- `POST /sessions/{session_id}/turn` with JSON `{ "text": "..." }`
- `POST /sessions/{session_id}/turn` with JSON `{ "audio_base64": "..." }`
- `POST /sessions/{session_id}/turn-stream` with JSON `{ "text": "...", "max_chunk_chars": 120 }`
- `POST /sessions/{session_id}/turn-stream` with JSON `{ "audio_base64": "...", "max_chunk_chars": 120 }`
- `GET /sessions/{session_id}/turn-stream-sse?text=...&max_chunk_chars=120`
- `GET /sessions/{session_id}/turn-stream-sse?audio_base64=...&language=pt-BR&max_chunk_chars=120`
- `POST /sessions/{session_id}/interrupt`
- `POST /sessions/{session_id}/end`
- `POST /tools/register-mcp` with JSON:
  - `{ "server_url": "http://host:port/mcp" }`
  - optional: `auth_token`, `allowlist`, `timeout_seconds`, `policy`
- `POST /providers/switch` with JSON:
  - `{ "kind": "stt|tts|llm", "name": "<registered-provider-name>" }`

Tool invocation shortcut for local testing with rule-based LLM:
- send `"/tool <tool_name> {\"arg\":\"value\"}"` as turn text.

MCP flow:
- register remote MCP tools through `/tools/register-mcp`
- tools become available in `GET /tools`
- invoke through regular turns using the `/tool ...` shortcut

Provider switching flow:
- providers are registered in runtime (local defaults are preloaded)
- switch active provider manually with `/providers/switch`
- inspect active providers with `GET /providers`

SSE streaming flow:
- use `turn-stream-sse` to receive incremental events as they are produced
- event types include `transcript`, `turn_started`, `llm_chunk`, `tts_chunk`, `tool_result`, `turn_completed`

The current baseline is framework-oriented; STT/TTS/LLM providers and transport
implementations can now be plugged in through the interfaces in `core/contracts.py`.
