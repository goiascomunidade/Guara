from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClientMessage:
    type: str
    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ClientMessage":
        if "type" not in raw:
            raise ValueError("client message missing 'type'")
        payload = {k: v for k, v in raw.items() if k != "type"}
        return cls(type=str(raw["type"]), payload=payload)


@dataclass(frozen=True)
class ServerMessage:
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        out = {"type": self.type}
        out.update(self.payload)
        return out

