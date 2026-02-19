from __future__ import annotations

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

