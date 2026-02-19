from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ProviderKind = str


@dataclass(frozen=True)
class ProviderInfo:
    kind: ProviderKind
    name: str
    is_active: bool


class ProviderRegistry:
    """Registry with manual switch support for STT/TTS/LLM providers."""

    def __init__(self) -> None:
        self._providers: dict[ProviderKind, dict[str, Any]] = {}
        self._active_names: dict[ProviderKind, str] = {}

    def register(
        self,
        *,
        kind: ProviderKind,
        name: str,
        provider: Any,
        activate: bool | None = None,
    ) -> None:
        bucket = self._providers.setdefault(kind, {})
        bucket[name] = provider
        if activate is True:
            self._active_names[kind] = name
            return
        if activate is None and kind not in self._active_names:
            self._active_names[kind] = name

    def switch(self, *, kind: ProviderKind, name: str) -> Any:
        bucket = self._providers.get(kind, {})
        if name not in bucket:
            raise KeyError(f"provider not found for kind={kind}: {name}")
        self._active_names[kind] = name
        return bucket[name]

    def get_active(self, kind: ProviderKind) -> Any:
        active = self._active_names.get(kind)
        if not active:
            raise KeyError(f"no active provider for kind: {kind}")
        return self._providers[kind][active]

    def get_active_name(self, kind: ProviderKind) -> str | None:
        return self._active_names.get(kind)

    def list(self) -> list[ProviderInfo]:
        payload: list[ProviderInfo] = []
        for kind, bucket in self._providers.items():
            active = self._active_names.get(kind)
            for name in sorted(bucket.keys()):
                payload.append(ProviderInfo(kind=kind, name=name, is_active=(name == active)))
        payload.sort(key=lambda item: (item.kind, item.name))
        return payload

