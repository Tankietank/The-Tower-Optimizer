"""Build a sanitized source ZIP and SHA-256 checksum."""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tower_optimizer import __version__

EXCLUDED_PARTS = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".log"}
ALLOWED_DATA = {Path("data/.gitkeep"), Path("data/README.md")}


def include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if rel.parts and rel.parts[0] == "data" and rel not in ALLOWED_DATA:
        return False
    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def main() -> int:
    out_dir = ROOT / "dist"
    out_dir.mkdir(exist_ok=True)
    archive = out_dir / f"tower-optimizer-{__version__}-source.zip"
    prefix = f"tower-optimizer-{__version__}"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(ROOT.rglob("*")):
            if include(path):
                rel = path.relative_to(ROOT)
                zf.write(path, Path(prefix) / rel)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
