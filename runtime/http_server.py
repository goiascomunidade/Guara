from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from runtime.app import GuaraRuntime


class GuaraHTTPServer:
    """Simple HTTP API wrapper around GuaraRuntime."""

    def __init__(self, runtime: GuaraRuntime | None = None) -> None:
        self.runtime = runtime or GuaraRuntime()
        self._httpd: ThreadingHTTPServer | None = None

    def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        runtime = self.runtime

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, status_code: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8"))

            def _run(self, coro):
                return asyncio.run(coro)

            def _send_sse_headers(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

            def _send_sse_event(self, event_type: str, payload: dict) -> None:
                data = json.dumps(payload, ensure_ascii=True)
                blob = f"event: {event_type}\ndata: {data}\n\n".encode("utf-8")
                self.wfile.write(blob)
                self.wfile.flush()

            def _stream_async_events(self, stream) -> None:
                loop = asyncio.new_event_loop()
                try:
                    while True:
                        try:
                            item = loop.run_until_complete(stream.__anext__())
                        except StopAsyncIteration:
                            break
                        event_type = str(item.get("type", "message"))
                        self._send_sse_event(event_type, item)
                finally:
                    try:
                        loop.run_until_complete(stream.aclose())
                    except Exception:
                        pass
                    loop.close()

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/health":
                    self._send_json(200, {"status": "ok"})
                    return

                if parsed.path == "/events":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", ["100"])[0])
                    event_name = query.get("event_name", [None])[0]
                    session_id = query.get("session_id", [None])[0]
                    response = self._run(
                        runtime.get_events(
                            limit=limit,
                            event_name=event_name,
                            session_id=session_id,
                        )
                    )
                    self._send_json(200, response)
                    return

                if parsed.path == "/tools":
                    response = self._run(runtime.list_tools())
                    self._send_json(200, response)
                    return

                if parsed.path == "/providers":
                    response = self._run(runtime.list_providers())
                    self._send_json(200, response)
                    return

                if parsed.path == "/sessions/start":
                    query = parse_qs(parsed.query)
                    user_id = query.get("user_id", [None])[0]
                    session_id = query.get("session_id", [None])[0]
                    response = self._run(runtime.start_session(user_id=user_id, session_id=session_id))
                    self._send_json(200, response)
                    return

                if parsed.path.startswith("/sessions/"):
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) == 3:
                        _, session_id, action = parts
                        if action == "turn-stream-sse":
                            query = parse_qs(parsed.query)
                            max_chunk_chars = int(query.get("max_chunk_chars", ["120"])[0])
                            text = query.get("text", [None])[0]
                            audio_base64 = query.get("audio_base64", [None])[0]

                            self._send_sse_headers()
                            if audio_base64 is not None:
                                import base64

                                audio = base64.b64decode(audio_base64)
                                stream = runtime.stream_audio_turn_events(
                                    session_id,
                                    audio,
                                    language=query.get("language", [None])[0],
                                    max_chunk_chars=max_chunk_chars,
                                )
                            else:
                                stream = runtime.stream_text_turn_events(
                                    session_id,
                                    text or "",
                                    max_chunk_chars=max_chunk_chars,
                                )
                            self._stream_async_events(stream)
                            self._send_sse_event("done", {"status": "ok"})
                            return

                self._send_json(404, {"error": "not_found"})

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                payload = self._read_json()
                try:
                    if parsed.path == "/tools/register-mcp":
                        policy_payload = payload.get("policy", {})
                        policy = None
                        if policy_payload:
                            from core.tool_runtime import ToolPolicy

                            policy = ToolPolicy(
                                cancel_on_interruption=bool(
                                    policy_payload.get("cancel_on_interruption", True)
                                ),
                                timeout_seconds=float(policy_payload.get("timeout_seconds", 10.0)),
                            )
                        response = self._run(
                            runtime.register_mcp_tools(
                                server_url=payload.get("server_url", ""),
                                auth_token=payload.get("auth_token"),
                                allowlist=payload.get("allowlist"),
                                timeout_seconds=float(payload.get("timeout_seconds", 5.0)),
                                policy=policy,
                            )
                        )
                        self._send_json(200, response)
                        return

                    if parsed.path == "/providers/switch":
                        response = self._run(
                            runtime.switch_provider(
                                kind=payload.get("kind", ""),
                                name=payload.get("name", ""),
                            )
                        )
                        self._send_json(200, response)
                        return

                    if parsed.path == "/sessions/start":
                        response = self._run(
                            runtime.start_session(
                                user_id=payload.get("user_id"),
                                session_id=payload.get("session_id"),
                            )
                        )
                        self._send_json(200, response)
                        return

                    if parsed.path.startswith("/sessions/"):
                        parts = parsed.path.strip("/").split("/")
                        if len(parts) != 3:
                            self._send_json(404, {"error": "not_found"})
                            return
                        _, session_id, action = parts

                        if action == "turn":
                            if "audio_base64" in payload:
                                import base64

                                audio = base64.b64decode(payload["audio_base64"])
                                response = self._run(
                                    runtime.process_audio_turn(
                                        session_id,
                                        audio,
                                        language=payload.get("language"),
                                    )
                                )
                            else:
                                response = self._run(
                                    runtime.process_text_turn(
                                        session_id,
                                        payload.get("text", ""),
                                    )
                                )
                            self._send_json(200, response)
                            return

                        if action == "turn-stream":
                            if "audio_base64" in payload:
                                import base64

                                audio = base64.b64decode(payload["audio_base64"])
                                response = self._run(
                                    runtime.process_audio_turn_stream(
                                        session_id,
                                        audio,
                                        language=payload.get("language"),
                                        max_chunk_chars=int(payload.get("max_chunk_chars", 120)),
                                    )
                                )
                            else:
                                response = self._run(
                                    runtime.process_text_turn_stream(
                                        session_id,
                                        payload.get("text", ""),
                                        max_chunk_chars=int(payload.get("max_chunk_chars", 120)),
                                    )
                                )
                            self._send_json(200, response)
                            return

                        if action == "interrupt":
                            response = self._run(runtime.interrupt_session(session_id))
                            self._send_json(200, response)
                            return

                        if action == "end":
                            response = self._run(runtime.end_session(session_id))
                            self._send_json(200, response)
                            return

                    self._send_json(404, {"error": "not_found"})
                except Exception as exc:  # pragma: no cover
                    self._send_json(500, {"error": str(exc)})

            def log_message(self, format, *args):  # noqa: A003
                return

        self._httpd = ThreadingHTTPServer((host, port), Handler)
        self._httpd.serve_forever()

    def shutdown(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
