from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.types import AutonomyMode, RiskLevel


@dataclass(frozen=True)
class FunctionSchema:
    name: str
    description: str
    properties: dict[str, dict[str, Any]] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("function name is required")
        if not self.description.strip():
            raise ValueError("function description is required")
        unknown_required = [name for name in self.required if name not in self.properties]
        if unknown_required:
            raise ValueError(f"required keys missing from properties: {unknown_required}")


@dataclass
class ToolsSchema:
    standard_tools: list[FunctionSchema] = field(default_factory=list)
    custom_tools: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def validate(self) -> None:
        for tool in self.standard_tools:
            tool.validate()

    def get(self, name: str) -> FunctionSchema | None:
        for tool in self.standard_tools:
            if tool.name == name:
                return tool
        return None


@dataclass(frozen=True)
class ToolSpec:
    id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: RiskLevel = RiskLevel.LOW
    autonomy_modes: set[AutonomyMode] = field(
        default_factory=lambda: {AutonomyMode.MANUAL, AutonomyMode.SCHEDULE, AutonomyMode.AUTONOMOUS}
    )


@dataclass(frozen=True)
class ToolExecutionContext:
    session_id: str
    trace_id: str
    user_id: str | None = None
    deadline_ms: int = 10_000
    consent_token: str | None = None


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    function_name: str
    arguments: dict[str, Any]
    depends_on: set[str] = field(default_factory=set)
    run_llm: bool = True


@dataclass(frozen=True)
class ToolExecutionResult:
    call_id: str
    function_name: str
    success: bool
    result: Any = None
    error: str | None = None
    run_llm: bool = True

