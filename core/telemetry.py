from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.events import EventRecord


class LocalEventStore:
    """Local-first in-memory event store with optional JSONL persistence."""

    def __init__(self, *, max_events: int = 2_000, jsonl_path: str | None = None) -> None:
        self._events: deque[EventRecord] = deque(maxlen=max_events)
        self._jsonl_path = Path(jsonl_path) if jsonl_path else None

    async def handle_event(self, record: EventRecord) -> None:
        self._events.append(record)
        if self._jsonl_path:
            self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            payload = self._record_to_dict(record)
            with self._jsonl_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def list_events(
        self,
        *,
        limit: int = 100,
        event_name: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        selected: list[EventRecord] = []
        for record in reversed(self._events):
            if event_name and record.event_name != event_name:
                continue
            if session_id and record.session_id != session_id:
                continue
            selected.append(record)
            if len(selected) >= limit:
                break
        return [self._record_to_dict(item) for item in selected]

    @staticmethod
    def _record_to_dict(record: EventRecord) -> dict[str, Any]:
        payload = asdict(record)
        created = payload.get("created_at")
        if isinstance(created, datetime):
            payload["created_at"] = created.isoformat()
        return payload

