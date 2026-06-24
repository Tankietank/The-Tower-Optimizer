"""Portable Windows entry point for Tower Optimizer (PyInstaller / dev smoke test).

Sets a writable profile data directory, starts Streamlit headlessly on localhost,
and opens the default browser. Double-click the packaged executable to run.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def _executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _bundle_root()


def _default_data_dir(exe_dir: Path) -> Path:
    override = os.environ.get("TOWER_OPTIMIZER_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "TowerOptimizer"
    fallback = exe_dir / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _open_browser_when_ready(url: str, timeout_seconds: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", int(url.rsplit(":", 1)[-1])), timeout=0.4):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.35)


def main() -> int:
    bundle = _bundle_root()
    exe_dir = _executable_dir()
    data_dir = _default_data_dir(exe_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TOWER_OPTIMIZER_DATA_DIR", str(data_dir))

    app_path = bundle / "app.py"
    if not app_path.exists():
        print(f"Missing app entry point: {app_path}", file=sys.stderr)
        return 1

    port = _pick_port()
    url = f"http://127.0.0.1:{port}"
    threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]

    from streamlit.web import cli as stcli

    return int(stcli.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
