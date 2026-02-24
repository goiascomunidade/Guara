from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Protocol

from core.tools import ToolExecutionContext, ToolSpec
from core.types import TranscriptionChunk


class ISTTProvider(Protocol):
    @abstractmethod
    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str | None = None,
    ) -> AsyncIterator[TranscriptionChunk]:
        raise NotImplementedError


class ITTSProvider(Protocol):
    @abstractmethod
    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        raise NotImplementedError

    @abstractmethod
    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, session_id: str) -> None:
        raise NotImplementedError


class ILLMProvider(Protocol):
    @abstractmethod
    async def complete(self, messages: list[dict[str, Any]], tools: Any | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: Any | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError


class IToolProvider(Protocol):
    @property
    @abstractmethod
    def tool_spec(self) -> ToolSpec:
        raise NotImplementedError

    @abstractmethod
    async def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> Any:
        raise NotImplementedError


class IMemoryProvider(Protocol):
    @abstractmethod
    async def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    async def query(self, text: str, limit: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError


class IGuardrail(Protocol):
    @abstractmethod
    async def validate_input(self, content: str) -> tuple[bool, str | None]:
        raise NotImplementedError

    @abstractmethod
    async def validate_output(self, content: str) -> tuple[bool, str | None]:
        raise NotImplementedError

