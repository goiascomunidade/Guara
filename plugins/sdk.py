from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from core.contracts import IToolProvider
from core.manifest import ToolManifest
from core.tools import FunctionSchema, ToolExecutionContext, ToolSpec
from core.types import RiskLevel


def _annotation_to_json_type(annotation: Any) -> str:
    if annotation in (int,):
        return "integer"
    if annotation in (float,):
        return "number"
    if annotation in (bool,):
        return "boolean"
    if annotation in (dict,):
        return "object"
    if annotation in (list, tuple, set):
        return "array"
    return "string"


def infer_function_schema(handler: Callable[..., Any], *, name: str | None = None) -> FunctionSchema:
    signature = inspect.signature(handler)
    doc = inspect.getdoc(handler) or ""
    lines = [line.strip() for line in doc.splitlines() if line.strip()]
    description = lines[0] if lines else f"Execute {handler.__name__}"

    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    for param in signature.parameters.values():
        if param.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            raise ValueError(f"unsupported parameter kind for plugin function: {param.kind}")

        json_type = _annotation_to_json_type(param.annotation)
        properties[param.name] = {"type": json_type, "description": f"Parameter {param.name}"}
        if param.default is inspect._empty:
            required.append(param.name)

    schema = FunctionSchema(
        name=name or handler.__name__,
        description=description,
        properties=properties,
        required=required,
    )
    schema.validate()
    return schema


class DirectFunctionToolProvider(IToolProvider):
    """Wraps a direct Python function as a tool provider."""

    def __init__(
        self,
        handler: Callable[..., Any] | Callable[..., Awaitable[Any]],
        *,
        name: str | None = None,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> None:
        self._handler = handler
        self._schema = infer_function_schema(handler, name=name)
        self._tool_spec = ToolSpec(
            id=self._schema.name,
            name=self._schema.name,
            description=self._schema.description,
            input_schema={
                "type": "object",
                "properties": self._schema.properties,
                "required": self._schema.required,
            },
            output_schema={"type": "object"},
            risk_level=risk_level,
        )

    @property
    def tool_spec(self) -> ToolSpec:
        return self._tool_spec

    async def execute(self, arguments: dict[str, Any], _: ToolExecutionContext) -> Any:
        self._validate_arguments(arguments)
        result = self._handler(**arguments)
        if inspect.isawaitable(result):
            return await result
        return result

    def _validate_arguments(self, arguments: dict[str, Any]) -> None:
        for item in self._schema.required:
            if item not in arguments:
                raise ValueError(f"missing required argument: {item}")


class PluginLoader:
    """Loads plugin manifests from disk and validates compatibility."""

    def __init__(self, core_version: str) -> None:
        self._core_version = core_version

    def discover(self, directory: str | Path) -> list[Path]:
        base = Path(directory)
        if not base.exists():
            return []
        files = list(base.rglob("plugin.json"))
        return sorted(files)

    def validate_manifest(self, file_path: str | Path) -> ToolManifest:
        path = Path(file_path)
        payload = json.loads(path.read_text())
        manifest = ToolManifest.from_dict(payload)
        if not manifest.is_compatible_with_core(self._core_version):
            raise ValueError(
                f"plugin {manifest.name} not compatible with core version {self._core_version}"
            )
        return manifest

    def load(self, file_path: str | Path) -> ToolManifest:
        return self.validate_manifest(file_path)

