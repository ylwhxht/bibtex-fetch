"""Launch the local browser UI from either a checkout or an installed wheel."""

from __future__ import annotations

import argparse
import json
import os
import socket
import threading
import webbrowser
from pathlib import Path
from urllib.request import urlopen

import uvicorn

from . import __version__
from .config import data_directory


def main():
    parser = argparse.ArgumentParser(description="BibTeX Fetch — local crawling console")
    parser.add_argument("--version", action="version", version=f"BibTeX Fetch {__version__}")
    parser.add_argument("--port", type=int, default=8765, help="Local HTTP port (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser tab")
    parser.add_argument("--data-dir", type=Path, help="Directory for local jobs, logs and cache")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    if args.data_dir:
        os.environ["BIBTEX_FETCH_DATA_DIR"] = str(args.data_dir.expanduser().resolve())
    url = f"http://127.0.0.1:{args.port}"
    # Avoid opening an unrelated service when the requested port is occupied.
    with socket.socket() as sock:
        sock.settimeout(2)
        if sock.connect_ex(("127.0.0.1", args.port)) == 0:
            try:
                with urlopen(url + "/api/health", timeout=2) as response:
                    running = json.load(response)
                if running.get("app") == "bibtex-fetch":
                    print(f"BibTeX Fetch is already running: {url}")
                    print(
                        "The existing process keeps its data directory; use another port for a new one."
                    )
                    if not args.no_browser:
                        webbrowser.open(url)
                    return 0
            except (OSError, ValueError):
                pass
            print(f"Port {args.port} is occupied. Choose --port with an unused port.")
            return 1
    print(f"BibTeX Fetch: {url}")
    print(f"Local data: {data_directory()}")
    if not args.no_browser:
        timer = threading.Timer(1.5, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    # Importing the ASGI app happens only after --data-dir has been resolved.
    uvicorn.run("bibclean.app:app", host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
