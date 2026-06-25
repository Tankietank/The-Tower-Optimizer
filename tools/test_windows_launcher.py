"""Local smoke test for scripts/windows_launcher.py (dev or packaged).

Usage:
  python tools/test_windows_launcher.py
  python tools/test_windows_launcher.py --packaged dist/TowerOptimizer/TowerOptimizer.exe
"""
from __future__ import annotations

import argparse
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def _health_ok(port: int, timeout: float = 0.75) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace").strip().lower() == "ok"
    except OSError:
        return False


def _wait_for_port(port: int, timeout: float = 600.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _health_ok(port):
            return True
        time.sleep(0.5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Tower Optimizer Windows launcher")
    parser.add_argument(
        "--packaged",
        type=Path,
        help="Path to built TowerOptimizer.exe instead of python scripts/windows_launcher.py",
    )
    parser.add_argument("--timeout", type=float, default=600.0, help="Seconds to wait for startup")
    args = parser.parse_args()

    data_dir = Path(__file__).resolve().parents[1] / "data" / f"launcher-smoke-{uuid.uuid4().hex[:8]}"
    data_dir.mkdir(parents=True, exist_ok=True)
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["TOWER_OPTIMIZER_DATA_DIR"] = str(data_dir)

    if args.packaged:
        exe = args.packaged.resolve()
        if not exe.exists():
            print(f"Missing executable: {exe}")
            return 1
        cmd = [str(exe)]
        cwd = exe.parent
    else:
        cmd = [sys.executable, str(ROOT / "scripts" / "windows_launcher.py")]
        cwd = ROOT

    print(f"Starting: {' '.join(cmd)}")
    print(f"Data dir: {data_dir}")
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env)
    started = time.monotonic()
    try:
        log_path = data_dir / "launcher.log"
        port = None
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                print(f"Process exited early with code {proc.returncode}")
                if log_path.exists():
                    print(log_path.read_text(encoding="utf-8", errors="replace")[-4000:])
                return 1
            if log_path.exists():
                text = log_path.read_text(encoding="utf-8", errors="replace")
                url_ports = re.findall(r"App URL: http://127\.0\.0\.1:(\d+)", text)
                uvicorn_ports = re.findall(
                    r"Uvicorn server started on 127\.0\.0\.1:(\d+)", text
                )
                if uvicorn_ports:
                    port = int(uvicorn_ports[-1])
                elif url_ports:
                    port = int(url_ports[-1])
            if port is not None and _health_ok(port):
                elapsed = time.monotonic() - started
                print(f"PASS: Streamlit healthy on port {port} after {elapsed:.1f}s")
                return 0
            time.sleep(0.5)
        print(f"FAIL: timed out after {args.timeout}s waiting for health check")
        if log_path.exists():
            print(log_path.read_text(encoding="utf-8", errors="replace")[-4000:])
        return 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
