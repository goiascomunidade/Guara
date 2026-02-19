from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from core.events import BargeInEvent, EventBus, TurnCompletedEvent, TurnStartedEvent, new_trace_id
from core.tool_runtime import ToolRouter
from core.types import SessionState


@dataclass
class Session:
    session_id: str
    user_id: str | None = None
    state: SessionState = SessionState.IDLE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    active_turn_id: str | None = None


class SessionController:
    """Session lifecycle controller for voice interactions."""

    def __init__(self, *, event_bus: EventBus | None = None, tool_router: ToolRouter | None = None):
        self._sessions: dict[str, Session] = {}
        self._event_bus = event_bus
        self._tool_router = tool_router

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def start_session(self, session_id: str, user_id: str | None = None) -> Session:
        session = Session(session_id=session_id, user_id=user_id, state=SessionState.LISTENING)
        self._sessions[session_id] = session
        return session

    async def push_audio_frame(self, session_id: str, _: bytes) -> str:
        session = self._require_session(session_id)
        if session.state in {SessionState.ENDED, SessionState.ERROR}:
            raise RuntimeError(f"session not accepting audio in state: {session.state.value}")

        turn_id = str(uuid4())
        session.active_turn_id = turn_id
        session.state = SessionState.THINKING

        if self._event_bus:
            await self._event_bus.publish(
                TurnStartedEvent(
                    trace_id=new_trace_id(),
                    session_id=session_id,
                    turn_id=turn_id,
                )
            )
        return turn_id

    async def mark_speaking(self, session_id: str) -> None:
        session = self._require_session(session_id)
        session.state = SessionState.SPEAKING

    async def complete_turn(self, session_id: str) -> None:
        session = self._require_session(session_id)
        turn_id = session.active_turn_id
        session.active_turn_id = None
        session.state = SessionState.LISTENING
        if self._event_bus and turn_id:
            await self._event_bus.publish(
                TurnCompletedEvent(
                    trace_id=new_trace_id(),
                    session_id=session_id,
                    turn_id=turn_id,
                )
            )

    async def interrupt(self, session_id: str) -> list[str]:
        session = self._require_session(session_id)
        session.state = SessionState.INTERRUPTED

        cancelled_calls: list[str] = []
        if self._tool_router:
            cancelled_calls = await self._tool_router.cancel_interruptible_calls()

        if self._event_bus:
            await self._event_bus.publish(
                BargeInEvent(
                    trace_id=new_trace_id(),
                    session_id=session_id,
                    cancelled_calls=cancelled_calls,
                )
            )

        session.state = SessionState.LISTENING
        return cancelled_calls

    async def end_session(self, session_id: str) -> None:
        session = self._require_session(session_id)
        session.state = SessionState.ENDED

    def _require_session(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"unknown session: {session_id}")
        return session

