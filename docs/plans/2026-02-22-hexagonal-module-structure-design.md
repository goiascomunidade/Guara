# Hexagonal Module Structure — Design Document

**Date**: 2026-02-22
**Status**: Approved
**Approach**: Hexagonal / Ports-and-Adapters

## Problem

`runtime/app.py` (GuaraRuntime, ~378 lines) is a god object that mixes session lifecycle, turn processing, provider management, tool routing, streaming, events, and MCP wiring. This makes individual subsystems hard to swap without touching unrelated code.

## Goal

Decompose GuaraRuntime into independently swappable subsystems following the hexagonal architecture pattern, with strict dependency direction rules.

## Dependency Rules

```
transport/ ──imports──▶ core/    (driving adapters call domain)
adapters/  ──imports──▶ core/    (driven adapters implement domain ports)
plugins/   ──imports──▶ core/    (extensions use domain contracts)
runtime/   ──imports──▶ ALL      (composition root wires everything)

core/      ──imports──▶ NOTHING  (pure domain, no external deps)
```

1. `core/` imports nothing outside itself — pure domain.
2. `adapters/` imports only from `core/` — implements outbound ports.
3. `transport/` imports only from `core/` — implements inbound ports.
4. `plugins/` imports only from `core/` — extends the domain.
5. `runtime/` is the only package that imports from all zones.
6. `transport/` must NOT import from `adapters/` (and vice versa).

## Core Domain Decomposition

Three domain services extracted from the current GuaraRuntime:

### Session Lifecycle — `core/session.py`

Already exists as `SessionController`. Enhanced to be the single authority for session lifecycle, absorbing the active-session tracking currently inline in `app.py`.

### Turn Processing Pipeline — `core/orchestrator.py`

Already exists. Focused to a pure pipeline: `input → guardrail → llm → tools → llm_followup → response`. Receives all dependencies (LLM provider, tool router, guardrails) via constructor injection. Knows nothing about HTTP, WebSocket, or provider registration.

### Provider Management — `core/provider_registry.py`

Already exists. Promoted to be the authority for registering, listing, and switching providers. Absorbs the manual wiring logic currently in `app.py.__init__` and `switch_provider()`.

### Unchanged Core Modules

- `contracts.py` — the 6 interfaces (ports)
- `tool_runtime.py` — ToolRouter
- `events.py` — EventBus
- `streaming.py` — chunking logic
- `summarizer.py` — summarization triggers
- `manifest.py` — plugin manifest validation
- `memory.py` — in-memory store
- `telemetry.py` — local event store
- `types.py` — shared types
- `tools.py` — tool schemas

## Transport Layer (New Package)

New top-level `transport/` package for driving adapters (inbound):

```
transport/
  __init__.py
  http_server.py        # FastAPI endpoints (moved from runtime/)
  websocket_server.py   # WS bidirectional transport (moved from runtime/)
  realtime.py           # Realtime event/channel manager (moved from runtime/)
  ws_protocol.py        # WS message definitions (moved from runtime/)
```

Transport files import from `core/` only. They receive domain services via injection, never construct providers. This enables swapping FastAPI for another framework without touching domain or adapter code.

## Adapters (Unchanged)

Kept flat as-is:

```
adapters/
  __init__.py
  stt_local.py
  tts_local.py
  llm_rule_based.py
  guardrail_basic.py
  mcp_http.py
  mcp_tool_provider.py
```

## Runtime as Composition Root

### `app.py` — Thin Facade (~50-80 lines)

GuaraRuntime becomes a composition root:

```python
class GuaraRuntime:
    def __init__(self, stt=None, tts=None, llm=None, guardrail=None, ...):
        self.providers = ProviderRegistry(stt, tts, llm, guardrail)
        self.event_bus = EventBus()
        self.tool_router = ToolRouter(...)
        self.sessions = SessionController(self.event_bus)
        self.orchestrator = Orchestrator(
            providers=self.providers,
            tool_router=self.tool_router,
            event_bus=self.event_bus,
        )

    def start_session(self, **kw):
        return self.sessions.start(**kw)

    def process_turn(self, session_id, text):
        return self.orchestrator.process(session_id, text)

    def switch_provider(self, kind, name):
        return self.providers.switch(kind, name)
```

**Discipline rule**: If any method is longer than 3-5 lines, logic has leaked into the facade and should be pushed into a domain service.

### `main.py` — Entry Point

```python
def main():
    runtime = GuaraRuntime()
    http = create_http_server(runtime)
    ws = create_ws_server(runtime)
    uvicorn.run(http, ...)
```

## Final Directory Structure

```
guara/
├── core/                     # Domain (the hexagon)
│   ├── __init__.py
│   ├── contracts.py          # Ports (6 interfaces)
│   ├── types.py
│   ├── session.py            # Session lifecycle service
│   ├── orchestrator.py       # Turn processing pipeline
│   ├── provider_registry.py  # Provider management service
│   ├── tool_runtime.py
│   ├── tools.py
│   ├── events.py
│   ├── streaming.py
│   ├── summarizer.py
│   ├── manifest.py
│   ├── memory.py
│   └── telemetry.py
├── adapters/                 # Driven adapters (outbound)
│   ├── __init__.py
│   ├── stt_local.py
│   ├── tts_local.py
│   ├── llm_rule_based.py
│   ├── guardrail_basic.py
│   ├── mcp_http.py
│   └── mcp_tool_provider.py
├── transport/                # Driving adapters (inbound) — NEW
│   ├── __init__.py
│   ├── http_server.py
│   ├── websocket_server.py
│   ├── realtime.py
│   └── ws_protocol.py
├── runtime/                  # Composition root
│   ├── __init__.py
│   ├── app.py                # Thin GuaraRuntime facade
│   └── main.py
├── plugins/
│   ├── __init__.py
│   ├── sdk.py
│   └── examples/
├── policies/
│   └── defaults.py
├── tests/
│   ├── core/                 # Domain logic tests (fast, mocked)
│   ├── adapters/             # Adapter contract tests
│   ├── transport/            # Protocol translation tests
│   ├── integration/          # End-to-end wiring tests
│   └── test_architecture.py  # Boundary enforcement
└── docs/
```

## Testing Strategy

- **Core tests** (`tests/core/`): Domain services with mock providers. Fast, pure logic.
- **Adapter tests** (`tests/adapters/`): Each adapter tested against its contract.
- **Transport tests** (`tests/transport/`): HTTP/WS endpoints with test client and mock runtime.
- **Integration tests** (`tests/integration/`): Full wiring, fewer and slower.

## Boundary Enforcement

An architectural test prevents dependency rule drift:

```python
# tests/test_architecture.py
def test_core_has_no_external_imports():
    """core/ must not import from adapters/, transport/, or runtime/"""

def test_transport_does_not_import_adapters():
    """transport/ must not import from adapters/"""

def test_adapters_does_not_import_transport():
    """adapters/ must not import from transport/"""
```

## Migration Notes

- Move `runtime/http_server.py` → `transport/http_server.py`
- Move `runtime/websocket_server.py` → `transport/websocket_server.py`
- Move `runtime/realtime.py` → `transport/realtime.py`
- Move `runtime/ws_protocol.py` → `transport/ws_protocol.py`
- Extract provider wiring from `app.py` → `core/provider_registry.py`
- Extract session tracking from `app.py` → `core/session.py`
- Focus `core/orchestrator.py` to pure pipeline
- Slim `runtime/app.py` to thin facade
- Reorganize `tests/` into subdirectories by zone
- Add `tests/test_architecture.py` for boundary enforcement
