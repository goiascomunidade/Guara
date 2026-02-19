from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable
from uuid import uuid4


@dataclass(frozen=True)
class EventRecord:
    event_name: str
    event_version: int
    trace_id: str
    session_id: str | None
    created_at: datetime
    payload: dict[str, Any]


@dataclass(frozen=True)
class TypedEvent:
    trace_id: str
    session_id: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_version: int = 1

    @property
    def event_name(self) -> str:
        raise NotImplementedError

    def to_record(self) -> EventRecord:
        event_fields = {item.name for item in fields(TypedEvent)}
        payload = {k: v for k, v in asdict(self).items() if k not in event_fields}
        return EventRecord(
            event_name=self.event_name,
            event_version=self.event_version,
            trace_id=self.trace_id,
            session_id=self.session_id,
            created_at=self.created_at,
            payload=payload,
        )


@dataclass(frozen=True)
class TurnStartedEvent(TypedEvent):
    turn_id: str = ""

    @property
    def event_name(self) -> str:
        return "turn_started"


@dataclass(frozen=True)
class ToolCalledEvent(TypedEvent):
    tool_name: str = ""
    call_id: str = ""

    @property
    def event_name(self) -> str:
        return "tool_called"


@dataclass(frozen=True)
class TTSStartedEvent(TypedEvent):
    text_preview: str = ""

    @property
    def event_name(self) -> str:
        return "tts_started"


@dataclass(frozen=True)
class BargeInEvent(TypedEvent):
    cancelled_calls: list[str] | None = None

    @property
    def event_name(self) -> str:
        return "barge_in"


@dataclass(frozen=True)
class TurnCompletedEvent(TypedEvent):
    turn_id: str = ""

    @property
    def event_name(self) -> str:
        return "turn_completed"


@dataclass(frozen=True)
class TurnFailedEvent(TypedEvent):
    turn_id: str = ""
    error: str = ""

    @property
    def event_name(self) -> str:
        return "turn_failed"


@dataclass(frozen=True)
class ProviderSwitchedEvent(TypedEvent):
    provider_kind: str = ""
    provider_name: str = ""

    @property
    def event_name(self) -> str:
        return "provider_switched"


EventHandler = Callable[[EventRecord], Awaitable[None] | None]


class EventBus:
    """Lightweight async event bus with typed/versioned events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._all_handlers: list[EventHandler] = []
        self._lock = asyncio.Lock()

    async def subscribe(self, event_name: str, handler: EventHandler) -> None:
        async with self._lock:
            self._handlers.setdefault(event_name, []).append(handler)

    async def subscribe_all(self, handler: EventHandler) -> None:
        async with self._lock:
            self._all_handlers.append(handler)

    async def publish(self, event: TypedEvent) -> None:
        record = event.to_record()
        async with self._lock:
            handlers = list(self._handlers.get(record.event_name, []))
            handlers.extend(self._all_handlers)
        for handler in handlers:
            result = handler(record)
            if asyncio.iscoroutine(result):
                await result


def new_trace_id() -> str:
    return str(uuid4())
