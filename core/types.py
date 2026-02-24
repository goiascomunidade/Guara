from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SessionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    TOOL_RUNNING = "tool_running"
    ERROR = "error"
    ENDED = "ended"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AutonomyMode(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    AUTONOMOUS = "autonomous"


@dataclass(frozen=True)
class TranscriptionChunk:
    text: str
    is_final: bool
    confidence: float = 1.0

