from __future__ import annotations

import argparse
import json
import socket
import threading
import webbrowser
from pathlib import Path

import uvicorn

from .analysis import analyze
from .app import app
from .fixture import write_fixture, write_spa_demo
from .ingest import IbtReader, read_npz


def free_port(preferred: int = 8765) -> int:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(prog="iracing-analyst")
    sub = parser.add_subparsers(dest="command")
    generate = sub.add_parser("generate-fixture")
    generate.add_argument("path", type=Path)
    demo = sub.add_parser("generate-demo")
    demo.add_argument("path", type=Path)
    analyze_command = sub.add_parser("analyze")
    analyze_command.add_argument("path", type=Path)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if args.command == "generate-fixture":
        write_fixture(args.path)
        print(args.path)
        return
    if args.command == "generate-demo":
        write_spa_demo(args.path)
        print(args.path)
        return
    if args.command == "analyze":
        run = IbtReader().read(args.path) if args.path.suffix.lower() == ".ibt" else read_npz(args.path)
        print(json.dumps(analyze(run).model_dump(mode="json"), ensure_ascii=False, indent=2))
        return
    port = getattr(args, "port", 0) or free_port()
    threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
