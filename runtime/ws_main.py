from __future__ import annotations

import argparse
import asyncio

from runtime.websocket_server import GuaraWebSocketServer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Guara WebSocket runtime")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = GuaraWebSocketServer()
    asyncio.run(server.serve(host=args.host, port=args.port))


if __name__ == "__main__":
    main()

