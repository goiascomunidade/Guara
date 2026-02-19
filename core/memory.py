from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryItem:
    value: Any
    expires_at: float | None = None


class LocalMemoryStore:
    """In-memory short-term store with TTL support."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    async def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires = time.time() + ttl_seconds if ttl_seconds is not None else None
        self._items[key] = MemoryItem(value=value, expires_at=expires)

    async def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if item is None:
            return None
        if item.expires_at is not None and time.time() > item.expires_at:
            self._items.pop(key, None)
            return None
        return item.value

    async def query(self, text: str, limit: int = 5) -> list[dict[str, Any]]:
        lowered = text.lower()
        results: list[dict[str, Any]] = []
        for key, item in self._items.items():
            if item.expires_at is not None and time.time() > item.expires_at:
                continue
            serialized = str(item.value).lower()
            if lowered in key.lower() or lowered in serialized:
                results.append({"key": key, "value": item.value})
            if len(results) >= limit:
                break
        return results

