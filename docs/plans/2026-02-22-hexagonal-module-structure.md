# Hexagonal Module Structure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Decompose GuaraRuntime god object into a hexagonal architecture with strict dependency rules, separate transport layer, and architectural boundary enforcement.

**Architecture:** The system is organized into five zones: `core/` (pure domain, no external imports), `adapters/` (outbound implementations, imports only core/), `transport/` (inbound HTTP/WS, imports core/ and runtime/), `runtime/` (composition root, imports everything), and `plugins/` (extensions, imports only core/). Transport and adapters must never cross-import.

**Tech Stack:** Python 3.11+, pytest, no new dependencies.

---

### Task 1: Establish baseline

**Files:**
- None modified

**Step 1: Run the existing test suite**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/ -v`
Expected: All tests PASS. If any fail, stop and investigate before proceeding.

**Step 2: Record passing test count**

Note the total number of passing tests. Every subsequent task must maintain this count.

---

### Task 2: Create transport/ package and move transport files

**Files:**
- Create: `transport/__init__.py`
- Move: `runtime/http_server.py` → `transport/http_server.py`
- Move: `runtime/realtime.py` → `transport/realtime.py`
- Move: `runtime/websocket_server.py` → `transport/websocket_server.py`
- Move: `runtime/ws_protocol.py` → `transport/ws_protocol.py`
- Move: `runtime/ws_main.py` → `transport/ws_main.py`
- Modify: `tests/test_realtime_manager.py`

**Step 1: Create transport package**

```python
# transport/__init__.py
"""Transport layer — driving adapters for HTTP, WebSocket, and SSE."""
```

**Step 2: Move tracked file with git mv**

```bash
git mv runtime/http_server.py transport/http_server.py
```

**Step 3: Move untracked files**

```bash
mv runtime/realtime.py transport/realtime.py
mv runtime/websocket_server.py transport/websocket_server.py
mv runtime/ws_protocol.py transport/ws_protocol.py
mv runtime/ws_main.py transport/ws_main.py
```

**Step 4: Fix imports in transport/realtime.py**

Change:
```python
from runtime.ws_protocol import ClientMessage
```
To:
```python
from transport.ws_protocol import ClientMessage
```

Note: `from runtime.app import GuaraRuntime` stays — transport is allowed to import from runtime/ (the composition root).

**Step 5: Fix imports in transport/websocket_server.py**

Change:
```python
from runtime.realtime import RealtimeSessionManager
```
To:
```python
from transport.realtime import RealtimeSessionManager
```

Note: `from runtime.app import GuaraRuntime` stays.

**Step 6: Fix imports in transport/ws_main.py**

Change:
```python
from runtime.websocket_server import GuaraWebSocketServer
```
To:
```python
from transport.websocket_server import GuaraWebSocketServer
```

**Step 7: Fix imports in tests/test_realtime_manager.py**

Change:
```python
from runtime.realtime import RealtimeSessionManager
```
To:
```python
from transport.realtime import RealtimeSessionManager
```

Note: `from runtime.app import GuaraRuntime` stays.

**Step 8: Run tests**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/ -v`
Expected: All tests PASS with same count as baseline.

**Step 9: Commit**

```bash
git add transport/ tests/test_realtime_manager.py
git commit -m "refactor: create transport/ package, move HTTP/WS from runtime/"
```

---

### Task 3: Add sync wiring to EventBus and remove lazy init from GuaraRuntime

The `_ensure_event_store_attached()` method is called in almost every public method of GuaraRuntime. This lazy-init boilerplate should be replaced with eager wiring in the constructor.

**Files:**
- Modify: `core/events.py`
- Test: `tests/test_event_bus.py`
- Modify: `runtime/app.py`

**Step 1: Write the failing test for sync subscribe**

Add to `tests/test_event_bus.py`:

```python
class TestEventBusSyncWiring(unittest.IsolatedAsyncioTestCase):
    async def test_subscribe_all_sync_receives_events(self) -> None:
        bus = EventBus()
        seen = []

        async def handler(record):
            seen.append(record)

        bus.subscribe_all_sync(handler)
        await bus.publish(TurnStartedEvent(trace_id="t-sync", session_id="s-sync", turn_id="turn-sync"))

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].payload["turn_id"], "turn-sync")
```

**Step 2: Run test to verify it fails**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/test_event_bus.py::TestEventBusSyncWiring -v`
Expected: FAIL with `AttributeError: 'EventBus' object has no attribute 'subscribe_all_sync'`

**Step 3: Add subscribe_all_sync to EventBus**

In `core/events.py`, add after the `subscribe_all` method (after line 127):

```python
    def subscribe_all_sync(self, handler: EventHandler) -> None:
        """Synchronous subscribe for use during initial wiring (e.g. in __init__)."""
        self._all_handlers.append(handler)
```

**Step 4: Run test to verify it passes**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/test_event_bus.py -v`
Expected: All event bus tests PASS.

**Step 5: Replace lazy init in GuaraRuntime**

In `runtime/app.py`, make these changes:

1. In `__init__`, after `self.event_store = LocalEventStore()` (line 35), add:
```python
        self.event_bus.subscribe_all_sync(self.event_store.handle_event)
```

2. Remove the `_event_store_attached` field (line 36).

3. Delete the entire `_ensure_event_store_attached` method (lines 70-74).

4. Remove all `await self._ensure_event_store_attached()` calls from every method that has them:
   - `register_provider` (line 87)
   - `switch_provider` (line 94)
   - `list_providers` (line 121)
   - `start_session` (line 129)
   - `process_audio_turn` (line 195)
   - `stream_audio_turn_events` (line 286)
   - `interrupt_session` (line 297)
   - `end_session` (line 302)
   - `register_mcp_tools` (line 315)
   - `get_events` (line 343)
   - `list_tools` (line 353)
   - `_run_turn` (line 368)

**Step 6: Run all tests**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 7: Commit**

```bash
git add core/events.py runtime/app.py tests/test_event_bus.py
git commit -m "refactor: eager event store wiring, remove lazy init boilerplate"
```

---

### Task 4: Simplify provider switching in GuaraRuntime

Currently GuaraRuntime caches `self.stt_provider`, `self.tts_provider`, `self.llm_provider` as separate fields and has `_apply_provider_switch()` with a kind-switch. Replace with direct registry lookups.

**Files:**
- Modify: `runtime/app.py`

**Step 1: Replace cached provider references with property lookups**

In `runtime/app.py`, replace the three cached assignments (lines 60-62):
```python
        self.stt_provider = self.provider_registry.get_active("stt")
        self.tts_provider = self.provider_registry.get_active("tts")
        self.llm_provider = self.provider_registry.get_active("llm")
```

With three properties (add after `__init__`):
```python
    @property
    def stt_provider(self):
        return self.provider_registry.get_active("stt")

    @property
    def tts_provider(self):
        return self.provider_registry.get_active("tts")

    @property
    def llm_provider(self):
        return self.provider_registry.get_active("llm")
```

**Step 2: Simplify switch_provider**

Replace the `switch_provider` and `_apply_provider_switch` methods with:

```python
    async def switch_provider(self, *, kind: str, name: str) -> dict:
        self.provider_registry.switch(kind=kind, name=name)
        if kind == "llm":
            self.orchestrator.set_llm_provider(self.provider_registry.get_active("llm"))
        await self.event_bus.publish(
            ProviderSwitchedEvent(
                trace_id=new_trace_id(),
                session_id=None,
                provider_kind=kind,
                provider_name=name,
            )
        )
        return {"kind": kind, "name": name, "active": True}
```

**Step 3: Simplify register_provider**

Replace with:

```python
    async def register_provider(self, *, kind: str, name: str, provider, activate: bool = False) -> dict:
        self.provider_registry.register(kind=kind, name=name, provider=provider, activate=activate)
        if activate:
            if kind == "llm":
                self.orchestrator.set_llm_provider(provider)
            await self.event_bus.publish(
                ProviderSwitchedEvent(
                    trace_id=new_trace_id(),
                    session_id=None,
                    provider_kind=kind,
                    provider_name=name,
                )
            )
        return {"kind": kind, "name": name, "active": activate}
```

**Step 4: Delete `_apply_provider_switch` method entirely**

Remove the `_apply_provider_switch` method.

**Step 5: Remove the guardrail field duplication**

In `__init__`, the guardrail is stored as `self.guardrail` and also passed to the orchestrator. Remove the `self.guardrail` field since it's only used by the orchestrator:

```python
        guardrail_instance = guardrail or BasicGuardrail()
        self.orchestrator = Orchestrator(
            llm_provider=self.llm_provider,
            tool_router=self.tool_router,
            guardrail=guardrail_instance,
        )
```

**Step 6: Run all tests**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 7: Commit**

```bash
git add runtime/app.py
git commit -m "refactor: replace cached provider refs with registry lookups"
```

---

### Task 5: Reorganize test directory structure

**Files:**
- Create: `tests/core/__init__.py`
- Create: `tests/transport/__init__.py`
- Create: `tests/integration/__init__.py`
- Move: `tests/test_event_bus.py` → `tests/core/test_event_bus.py`
- Move: `tests/test_manifest.py` → `tests/core/test_manifest.py`
- Move: `tests/test_session.py` → `tests/core/test_session.py`
- Move: `tests/test_streaming.py` → `tests/core/test_streaming.py`
- Move: `tests/test_summarizer.py` → `tests/core/test_summarizer.py`
- Move: `tests/test_tool_runtime.py` → `tests/core/test_tool_runtime.py`
- Move: `tests/test_plugin_sdk.py` → `tests/core/test_plugin_sdk.py`
- Move: `tests/test_runtime_app.py` → `tests/integration/test_runtime_app.py`
- Move: `tests/test_mcp_integration.py` → `tests/integration/test_mcp_integration.py`
- Move: `tests/test_realtime_manager.py` → `tests/transport/test_realtime_manager.py`

**Step 1: Create subdirectory __init__.py files**

```python
# tests/core/__init__.py
# tests/transport/__init__.py
# tests/integration/__init__.py
```

All three files are empty (just the comment line above or completely empty).

**Step 2: Move tracked test files with git mv**

```bash
mkdir -p tests/core tests/transport tests/integration
git mv tests/test_event_bus.py tests/core/test_event_bus.py
git mv tests/test_manifest.py tests/core/test_manifest.py
git mv tests/test_session.py tests/core/test_session.py
git mv tests/test_streaming.py tests/core/test_streaming.py
git mv tests/test_summarizer.py tests/core/test_summarizer.py
git mv tests/test_tool_runtime.py tests/core/test_tool_runtime.py
git mv tests/test_plugin_sdk.py tests/core/test_plugin_sdk.py
git mv tests/test_runtime_app.py tests/integration/test_runtime_app.py
git mv tests/test_mcp_integration.py tests/integration/test_mcp_integration.py
```

**Step 3: Move untracked test file**

```bash
mv tests/test_realtime_manager.py tests/transport/test_realtime_manager.py
```

**Step 4: Run all tests**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/ -v`
Expected: All tests PASS. pytest discovers tests recursively in subdirectories.

**Step 5: Commit**

```bash
git add tests/
git commit -m "refactor: reorganize tests into core/, transport/, integration/ subdirectories"
```

---

### Task 6: Add architectural boundary enforcement test

**Files:**
- Create: `tests/test_architecture.py`

**Step 1: Write the boundary enforcement test**

```python
"""Architectural boundary tests for hexagonal dependency rules.

Rules enforced:
1. core/ must not import from adapters/, transport/, or runtime/
2. adapters/ must not import from transport/
3. transport/ must not import from adapters/
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _collect_imports(package_dir: Path) -> list[tuple[str, str]]:
    """Return list of (file_path, imported_module) for all .py files in package_dir."""
    results: list[tuple[str, str]] = []
    if not package_dir.exists():
        return results
    for py_file in sorted(package_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        relative = str(py_file.relative_to(PROJECT_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    results.append((relative, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    results.append((relative, node.module))
    return results


def _violations(imports: list[tuple[str, str]], forbidden_prefixes: list[str]) -> list[str]:
    """Return human-readable violation messages."""
    msgs: list[str] = []
    for file_path, module in imports:
        for prefix in forbidden_prefixes:
            if module == prefix or module.startswith(prefix + "."):
                msgs.append(f"{file_path} imports {module}")
    return msgs


class TestArchitecturalBoundaries(unittest.TestCase):
    def test_core_has_no_external_imports(self) -> None:
        """core/ must not import from adapters/, transport/, or runtime/."""
        imports = _collect_imports(PROJECT_ROOT / "core")
        violations = _violations(imports, ["adapters", "transport", "runtime"])
        self.assertEqual(violations, [], f"core/ boundary violations:\n" + "\n".join(violations))

    def test_adapters_does_not_import_transport(self) -> None:
        """adapters/ must not import from transport/."""
        imports = _collect_imports(PROJECT_ROOT / "adapters")
        violations = _violations(imports, ["transport"])
        self.assertEqual(violations, [], f"adapters/ boundary violations:\n" + "\n".join(violations))

    def test_transport_does_not_import_adapters(self) -> None:
        """transport/ must not import from adapters/."""
        imports = _collect_imports(PROJECT_ROOT / "transport")
        violations = _violations(imports, ["adapters"])
        self.assertEqual(violations, [], f"transport/ boundary violations:\n" + "\n".join(violations))

    def test_plugins_does_not_import_runtime_or_transport(self) -> None:
        """plugins/ must not import from runtime/ or transport/."""
        imports = _collect_imports(PROJECT_ROOT / "plugins")
        violations = _violations(imports, ["runtime", "transport"])
        self.assertEqual(violations, [], f"plugins/ boundary violations:\n" + "\n".join(violations))
```

**Step 2: Run the boundary test**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/test_architecture.py -v`
Expected: All 4 tests PASS. If any fail, there is an import that needs fixing.

**Step 3: Run full test suite**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/ -v`
Expected: All tests PASS (original count + 5 new tests: 1 sync wiring + 4 boundary).

**Step 4: Commit**

```bash
git add tests/test_architecture.py
git commit -m "test: add architectural boundary enforcement tests"
```

---

### Task 7: Final verification and commit

**Files:**
- None modified

**Step 1: Run full test suite one final time**

Run: `cd /home/peras/gitperaro/Guara && python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 2: Verify directory structure**

Run: `find /home/peras/gitperaro/Guara -name "*.py" -not -path "*/__pycache__/*" | sort`

Expected structure should show:
```
adapters/*.py          (flat, unchanged)
core/*.py              (unchanged)
transport/__init__.py
transport/http_server.py
transport/realtime.py
transport/websocket_server.py
transport/ws_main.py
transport/ws_protocol.py
runtime/__init__.py
runtime/app.py         (slimmed facade)
runtime/main.py
plugins/*.py           (unchanged)
tests/test_architecture.py
tests/core/test_*.py   (6-7 test files)
tests/transport/test_*.py
tests/integration/test_*.py
```

**Step 3: Verify no transport files remain in runtime/**

Run: `ls runtime/`
Expected: Only `__init__.py`, `app.py`, `main.py` remain.

**Step 4: Review git diff for the full refactoring**

Run: `git diff --stat HEAD~4` (or however many commits were made)
Review that the changes align with the design document.
