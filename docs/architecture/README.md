# Guara Architecture Notes

This folder contains architectural decisions and diagrams for the Guara core.

Current baseline:
- Typed, versioned internal events (`core/events.py`)
- Local-first event store for telemetry (`core/telemetry.py`)
- Tool runtime with bounded parallelism and interruption-aware cancellation (`core/tool_runtime.py`)
- Session lifecycle controller (`core/session.py`)
- Provider registry with manual switching (`core/provider_registry.py`)
- Streaming chunk helper for optimistic TTS (`core/streaming.py`)
- Runtime streaming generator + SSE transport path (`runtime/app.py`, `runtime/http_server.py`)
- Universal tools schema (`core/tools.py`)
- Plugin manifest + compatibility validation (`core/manifest.py`, `plugins/sdk.py`)
- MCP HTTP tool discovery/execution adapters (`adapters/mcp_http.py`, `adapters/mcp_tool_provider.py`)
