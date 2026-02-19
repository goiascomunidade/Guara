from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.types import AutonomyMode, RiskLevel

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+].*)?$")
SPEC_ITEM_RE = re.compile(r"^(>=|<=|>|<|==)\s*(\d+\.\d+\.\d+)$")


def _parse_semver(version: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(version)
    if not match:
        raise ValueError(f"invalid semver: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _compare_semver(left: str, op: str, right: str) -> bool:
    lv = _parse_semver(left)
    rv = _parse_semver(right)
    if op == "==":
        return lv == rv
    if op == ">":
        return lv > rv
    if op == ">=":
        return lv >= rv
    if op == "<":
        return lv < rv
    if op == "<=":
        return lv <= rv
    raise ValueError(f"unsupported operator: {op}")


def version_satisfies(version: str, spec: str) -> bool:
    for raw_item in spec.split(","):
        item = raw_item.strip()
        if not item:
            continue
        match = SPEC_ITEM_RE.match(item)
        if not match:
            raise ValueError(f"invalid version constraint: {item}")
        op, target = match.groups()
        if not _compare_semver(version, op, target):
            return False
    return True


@dataclass(frozen=True)
class ToolManifest:
    tool_id: str
    name: str
    version: str
    description: str
    capabilities: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permissions: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    autonomy_modes: set[AutonomyMode] = field(default_factory=lambda: {AutonomyMode.MANUAL})
    compatibility: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolManifest":
        risk_level = RiskLevel(payload.get("risk_level", RiskLevel.LOW.value))
        autonomy_modes = {
            AutonomyMode(mode) for mode in payload.get("autonomy_modes", [AutonomyMode.MANUAL.value])
        }
        manifest = cls(
            tool_id=payload["tool_id"],
            name=payload["name"],
            version=payload["version"],
            description=payload["description"],
            capabilities=list(payload.get("capabilities", [])),
            input_schema=dict(payload.get("input_schema", {})),
            output_schema=dict(payload.get("output_schema", {})),
            permissions=list(payload.get("permissions", [])),
            risk_level=risk_level,
            autonomy_modes=autonomy_modes,
            compatibility=dict(payload.get("compatibility", {})),
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if not self.tool_id.strip():
            raise ValueError("tool_id is required")
        if not self.name.strip():
            raise ValueError("name is required")
        if not self.description.strip():
            raise ValueError("description is required")
        if not self.capabilities:
            raise ValueError("capabilities cannot be empty")
        if not self.input_schema:
            raise ValueError("input_schema cannot be empty")
        if not self.output_schema:
            raise ValueError("output_schema cannot be empty")
        _parse_semver(self.version)

    def is_compatible_with_core(self, core_version: str) -> bool:
        spec = self.compatibility.get("guara_core")
        if not spec:
            return True
        return version_satisfies(core_version, spec)

