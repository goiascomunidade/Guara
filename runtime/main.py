from __future__ import annotations

import argparse

from runtime.http_server import GuaraHTTPServer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Guara HTTP runtime")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = GuaraHTTPServer()
    server.serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

