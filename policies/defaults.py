from __future__ import annotations

from core.tool_runtime import ToolPolicy

# Default runtime behavior:
# - Tools can be interrupted unless explicitly configured otherwise.
# - Keep timeout short to maintain voice responsiveness.
DEFAULT_TOOL_POLICY = ToolPolicy(cancel_on_interruption=True, timeout_seconds=10.0)

