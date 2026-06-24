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
import traceback
import webbrowser
from datetime import datetime, timezone
from pathlib import Path


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def _executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _bundle_root()


def _is_portable(exe_dir: Path) -> bool:
    flag = os.environ.get("TOWER_OPTIMIZER_PORTABLE", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    if (exe_dir / "portable.txt").is_file():
        return True
    return (exe_dir / "data" / ".portable").is_file()


def _default_data_dir(exe_dir: Path) -> Path:
    override = os.environ.get("TOWER_OPTIMIZER_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if _is_portable(exe_dir):
        data = exe_dir / "data"
        data.mkdir(parents=True, exist_ok=True)
        return data
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "TowerOptimizer"
    fallback = exe_dir / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _bootstrap_log(exe_dir: Path, message: str) -> None:
    try:
        with (exe_dir / "launcher.log").open("a", encoding="utf-8", errors="replace") as handle:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            handle.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def _setup_logging(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "launcher.log"
    log_handle = log_path.open("a", encoding="utf-8", errors="replace")

    def write_log(line: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        log_handle.write(f"[{stamp}] {line.rstrip()}\n")
        log_handle.flush()

    write_log("Tower Optimizer launcher starting")
    write_log(f"Log file: {log_path}")

    class _Tee:
        def __init__(self, stream, log_file):
            self._stream = stream
            self._log_file = log_file

        def write(self, data: str) -> int:
            if data:
                stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                self._log_file.write(f"[{stamp}] {data}")
                self._log_file.flush()
                if self._stream is not None:
                    try:
                        self._stream.write(data)
                        self._stream.flush()
                    except OSError:
                        pass
            return len(data)

        def flush(self) -> None:
            self._log_file.flush()
            if self._stream is not None:
                try:
                    self._stream.flush()
                except OSError:
                    pass

    sys.stdout = _Tee(getattr(sys, "__stdout__", None), log_handle)
    sys.stderr = _Tee(getattr(sys, "__stderr__", None), log_handle)
    return log_path


def _show_error(title: str, message: str) -> None:
    print(f"ERROR: {title}: {message}", file=sys.stderr)
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except OSError:
        pass


def _show_splash(message: str):
    try:
        import tkinter as tk

        root = tk.Tk()
        root.title("Tower Optimizer")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        frame = tk.Frame(root, padx=24, pady=20)
        frame.pack()
        tk.Label(frame, text=message, font=("Segoe UI", 11)).pack()
        root.update_idletasks()
        width = max(root.winfo_reqwidth(), 320)
        height = root.winfo_reqheight()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        root.geometry(f"{width}x{height}+{(screen_w - width) // 2}+{(screen_h - height) // 2}")
        root.update()
        return root
    except Exception:
        return None


def _pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _port_from_url(url: str) -> int:
    return int(url.rsplit(":", 1)[-1])


def _server_ready(port: int, timeout_seconds: float = 0.4) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _open_browser_when_ready(url: str, splash, timeout_seconds: float = 120.0) -> None:
    port = _port_from_url(url)
    deadline = time.monotonic() + timeout_seconds
    opened = False
    while time.monotonic() < deadline:
        if _server_ready(port):
            if splash is not None:
                try:
                    splash.destroy()
                except Exception:
                    pass
            if not opened:
                try:
                    opened = bool(webbrowser.open(url))
                except Exception as exc:
                    print(f"Could not open browser automatically: {exc}", file=sys.stderr)
                if not opened:
                    print(f"Open this URL in your browser: {url}")
            return
        time.sleep(0.35)
    if splash is not None:
        try:
            splash.destroy()
        except Exception:
            pass
    print(f"Timed out waiting for the app to start. Try opening: {url}", file=sys.stderr)


def main() -> int:
    splash = None
    try:
        bundle = _bundle_root()
        exe_dir = _executable_dir()
        data_dir = _default_data_dir(exe_dir)
        _bootstrap_log(exe_dir, f"Started — data folder: {data_dir}")
        _setup_logging(data_dir)
        os.chdir(exe_dir)
        os.environ.setdefault("TOWER_OPTIMIZER_DATA_DIR", str(data_dir))

        if getattr(sys, "frozen", False):
            bundle_str = str(bundle)
            if bundle_str not in sys.path:
                sys.path.insert(0, bundle_str)

        app_path = bundle / "app.py"
        if not app_path.exists():
            msg = f"Missing app entry point: {app_path}"
            _show_error("Tower Optimizer", msg)
            return 1

        splash = _show_splash("Starting Tower Optimizer...\nThis can take 10–30 seconds on first launch.")

        port = _pick_port()
        url = f"http://127.0.0.1:{port}"
        print(f"Using data folder: {data_dir}")
        print(f"App URL: {url}")
        threading.Thread(target=_open_browser_when_ready, args=(url, splash), daemon=True).start()

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
    except Exception as exc:
        if splash is not None:
            try:
                splash.destroy()
            except Exception:
                pass
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        print(detail, file=sys.stderr)
        _show_error(
            "Tower Optimizer",
            "Tower Optimizer could not start.\n\n"
            f"Details were saved to your data folder.\n\n{exc}",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
