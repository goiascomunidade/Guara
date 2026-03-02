from __future__ import annotations

import base64
from dataclasses import asdict
from uuid import uuid4

from adapters.guardrail_basic import BasicGuardrail
from adapters.llm_rule_based import RuleBasedLLMProvider
from adapters.mcp_http import MCPHTTPClient, MCPServerConfig
from adapters.mcp_tool_provider import discover_mcp_tool_providers
from adapters.stt_local import LocalSTTProvider
from adapters.tts_local import LocalTTSProvider
from core.events import EventBus, ProviderSwitchedEvent, TTSStartedEvent, new_trace_id
from core.orchestrator import Orchestrator
from core.provider_registry import ProviderRegistry
from core.session import SessionController
from core.streaming import split_text_for_streaming
from core.telemetry import LocalEventStore
from core.tool_runtime import ToolPolicy, ToolRouter


class GuaraRuntime:
    """Composable runtime that wires session, orchestration, and adapters."""

    def __init__(
        self,
        *,
        stt_provider=None,
        tts_provider=None,
        llm_provider=None,
        guardrail=None,
        max_parallel_calls: int = 3,
        system_prompt: str | None = None,
    ) -> None:
        self.event_bus = EventBus()
        self.event_store = LocalEventStore()
        self.event_bus.subscribe_all_sync(self.event_store.handle_event)
        self.tool_router = ToolRouter(max_parallel_calls=max_parallel_calls, event_bus=self.event_bus)
        self.session_controller = SessionController(event_bus=self.event_bus, tool_router=self.tool_router)
        self.provider_registry = ProviderRegistry()

        self.provider_registry.register(
            kind="stt",
            name="local",
            provider=stt_provider or LocalSTTProvider(),
            activate=True,
        )
        self.provider_registry.register(
            kind="tts",
            name="local",
            provider=tts_provider or LocalTTSProvider(),
            activate=True,
        )
        self.provider_registry.register(
            kind="llm",
            name="rule-based",
            provider=llm_provider or RuleBasedLLMProvider(),
            activate=True,
        )

        guardrail_instance = guardrail or BasicGuardrail()
        self.orchestrator = Orchestrator(
            llm_provider=self.llm_provider,
            tool_router=self.tool_router,
            guardrail=guardrail_instance,
            system_prompt=system_prompt,
        )

    @property
    def stt_provider(self):
        return self.provider_registry.get_active("stt")

    @property
    def tts_provider(self):
        return self.provider_registry.get_active("tts")

    @property
    def llm_provider(self):
        return self.provider_registry.get_active("llm")

    def register_tool(self, provider, policy: ToolPolicy | None = None) -> None:
        self.tool_router.register_tool(provider, policy=policy)

    async def register_provider(
        self,
        *,
        kind: str,
        name: str,
        provider,
        activate: bool = False,
    ) -> dict:
        self.provider_registry.register(kind=kind, name=name, provider=provider, activate=activate)
        if activate:
            if kind == "llm":
                self.orchestrator.set_llm_provider(self.provider_registry.get_active("llm"))
            await self.event_bus.publish(
                ProviderSwitchedEvent(
                    trace_id=new_trace_id(),
                    session_id=None,
                    provider_kind=kind,
                    provider_name=name,
                )
            )
        return {"kind": kind, "name": name, "active": activate}

    async def switch_provider(self, *, kind: str, name: str) -> dict:
        self.provider_registry.switch(kind=kind, name=name)
        if kind == "llm":
            self.orchestrator.set_llm_provider(self.provider_registry.get_active("llm"))
        await self.event_bus.publish(
            ProviderSwitchedEvent(
                trace_id=new_trace_id(),
                session_id=None,
                provider_kind=kind,
                provider_name=name,
            )
        )
        return {"kind": kind, "name": name, "active": True}

    async def list_providers(self) -> dict:
        providers = self.provider_registry.list()
        payload = [
            {"kind": item.kind, "name": item.name, "is_active": item.is_active} for item in providers
        ]
        return {"providers": payload}

    async def start_session(self, user_id: str | None = None, session_id: str | None = None) -> dict:
        sid = session_id or str(uuid4())
        session = await self.session_controller.start_session(sid, user_id=user_id)
        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "user_id": session.user_id,
        }

    async def process_text_turn(self, session_id: str, user_text: str) -> dict:
        turn_id, response = await self._run_turn(session_id, user_text)
        await self.event_bus.publish(
            TTSStartedEvent(
                trace_id=new_trace_id(),
                session_id=session_id,
                text_preview=response.reply_text[:80],
            )
        )
        audio = await self.tts_provider.synthesize(response.reply_text)
        await self.session_controller.complete_turn(session_id)

        return {
            "turn_id": turn_id,
            "reply_text": response.reply_text,
            "audio_base64": base64.b64encode(audio).decode("ascii"),
            "tool_results": [asdict(item) for item in response.tool_results],
        }

    async def process_text_turn_stream(
        self,
        session_id: str,
        user_text: str,
        *,
        max_chunk_chars: int = 120,
    ) -> dict:
        events: list[dict] = []
        turn_id = ""
        reply_text = ""
        tool_results: list[dict] = []

        async for event in self.stream_text_turn_events(
            session_id,
            user_text,
            max_chunk_chars=max_chunk_chars,
        ):
            events.append(event)
            if event["type"] == "turn_started":
                turn_id = event["turn_id"]
                reply_text = event.get("reply_text", "")
            elif event["type"] == "tool_result":
                tool_results.append(event["result"])

        return {
            "turn_id": turn_id,
            "reply_text": reply_text,
            "events": events,
            "tool_results": tool_results,
        }

    async def process_audio_turn(
        self,
        session_id: str,
        audio: bytes,
        *,
        language: str | None = None,
    ) -> dict:
        text = await self.stt_provider.transcribe(audio, language=language)
        result = await self.process_text_turn(session_id, text)
        result["transcript"] = text
        return result

    async def process_audio_turn_stream(
        self,
        session_id: str,
        audio: bytes,
        *,
        language: str | None = None,
        max_chunk_chars: int = 120,
    ) -> dict:
        events: list[dict] = []
        turn_id = ""
        reply_text = ""
        transcript = ""
        tool_results: list[dict] = []

        async for event in self.stream_audio_turn_events(
            session_id,
            audio,
            language=language,
            max_chunk_chars=max_chunk_chars,
        ):
            events.append(event)
            if event["type"] == "transcript":
                transcript = event.get("text", "")
            elif event["type"] == "turn_started":
                turn_id = event["turn_id"]
                reply_text = event.get("reply_text", "")
            elif event["type"] == "tool_result":
                tool_results.append(event["result"])

        return {
            "turn_id": turn_id,
            "reply_text": reply_text,
            "transcript": transcript,
            "events": events,
            "tool_results": tool_results,
        }

    async def stream_text_turn_events(
        self,
        session_id: str,
        user_text: str,
        *,
        max_chunk_chars: int = 120,
    ):
        turn_id, response = await self._run_turn(session_id, user_text)
        yield {
            "type": "turn_started",
            "turn_id": turn_id,
            "reply_text": response.reply_text,
        }

        chunks = split_text_for_streaming(response.reply_text, max_chunk_chars=max_chunk_chars)
        if not chunks and response.reply_text:
            chunks = [response.reply_text]

        for index, chunk in enumerate(chunks):
            await self.event_bus.publish(
                TTSStartedEvent(
                    trace_id=new_trace_id(),
                    session_id=session_id,
                    text_preview=chunk[:80],
                )
            )
            yield {"type": "llm_chunk", "index": index, "text": chunk}
            audio = await self.tts_provider.synthesize(chunk)
            yield {
                "type": "tts_chunk",
                "index": index,
                "audio_base64": base64.b64encode(audio).decode("ascii"),
            }

        for item in response.tool_results:
            yield {"type": "tool_result", "result": asdict(item)}

        await self.session_controller.complete_turn(session_id)
        yield {"type": "turn_completed", "turn_id": turn_id}

    async def stream_audio_turn_events(
        self,
        session_id: str,
        audio: bytes,
        *,
        language: str | None = None,
        max_chunk_chars: int = 120,
    ):
        text = await self.stt_provider.transcribe(audio, language=language)
        yield {"type": "transcript", "text": text}
        async for event in self.stream_text_turn_events(
            session_id,
            text,
            max_chunk_chars=max_chunk_chars,
        ):
            yield event

    async def interrupt_session(self, session_id: str) -> dict:
        cancelled = await self.session_controller.interrupt(session_id)
        return {"session_id": session_id, "cancelled_calls": cancelled}

    async def end_session(self, session_id: str) -> dict:
        await self.session_controller.end_session(session_id)
        return {"session_id": session_id, "state": "ended"}

    async def register_mcp_tools(
        self,
        *,
        server_url: str,
        auth_token: str | None = None,
        allowlist: list[str] | None = None,
        timeout_seconds: float = 5.0,
        policy: ToolPolicy | None = None,
    ) -> dict:
        if not server_url:
            raise ValueError("server_url is required")
        client = MCPHTTPClient(
            MCPServerConfig(
                url=server_url,
                auth_token=auth_token,
                timeout_seconds=timeout_seconds,
            )
        )
        providers = await discover_mcp_tool_providers(
            client,
            allowlist=set(allowlist) if allowlist else None,
        )
        for provider in providers:
            self.tool_router.register_tool(provider, policy=policy)
        return {
            "registered_count": len(providers),
            "registered_tools": [provider.tool_spec.name for provider in providers],
        }

    async def get_events(
        self,
        *,
        limit: int = 100,
        event_name: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        return {
            "events": self.event_store.list_events(
                limit=limit,
                event_name=event_name,
                session_id=session_id,
            )
        }

    async def list_tools(self) -> dict:
        names = self.tool_router.list_tools()
        payload = []
        for name in names:
            policy = self.tool_router.get_policy(name)
            payload.append(
                {
                    "name": name,
                    "cancel_on_interruption": policy.cancel_on_interruption,
                    "timeout_seconds": policy.timeout_seconds,
                }
            )
        return {"tools": payload}

    async def _run_turn(self, session_id: str, user_text: str):
        turn_id = await self.session_controller.push_audio_frame(session_id, b"")
        response = await self.orchestrator.handle_user_text(
            user_text,
            session_id=session_id,
            trace_id=new_trace_id(),
            user_id=self.session_controller.get_session(session_id).user_id,
        )
        await self.session_controller.mark_speaking(session_id)
        return turn_id, response
