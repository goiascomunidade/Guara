"""Guara CLI — unified entry point.

Usage:
    guara listen          Wake-word listener (microphone)
    guara serve           HTTP server (API + SSE)
    guara ws              WebSocket server
"""
from __future__ import annotations

import argparse
import os
import sys

# Ensure the project root is on sys.path so local packages (runtime, transport, etc.)
# are importable even when invoked via an installed entry-point script.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _cmd_listen(_args: argparse.Namespace) -> None:
    from runtime.listener_main import main as listener_main
    listener_main()


def _cmd_serve(args: argparse.Namespace) -> None:
    from runtime.main import main as http_main

    sys.argv = ["guara-serve"]
    if args.host:
        sys.argv += ["--host", args.host]
    if args.port:
        sys.argv += ["--port", str(args.port)]
    http_main()


def _cmd_ws(args: argparse.Namespace) -> None:
    import asyncio

    from transport.websocket_server import GuaraWebSocketServer

    server = GuaraWebSocketServer()
    asyncio.run(server.serve(host=args.host, port=args.port))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="guara",
        description="Guara voice-to-voice agent runtime",
    )
    sub = parser.add_subparsers(dest="command")

    # listen
    sub.add_parser("listen", help="Wake-word listener (microphone)")

    # serve
    srv = sub.add_parser("serve", help="HTTP server (API + SSE)")
    srv.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    srv.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")

    # ws
    ws = sub.add_parser("ws", help="WebSocket server")
    ws.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    ws.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "listen": _cmd_listen,
        "serve": _cmd_serve,
        "ws": _cmd_ws,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
