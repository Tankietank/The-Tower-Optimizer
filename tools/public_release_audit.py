"""Fail when a public source tree contains likely private or generated files."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".pytest_cache"}
FORBIDDEN_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".ods", ".csv", ".tsv", ".pem", ".p12", ".pfx", ".key"}
FORBIDDEN_NAME_PARTS = {"tanker", "diagnostic", "backup", "export"}
ALLOWED_DATA = {Path("data/.gitkeep"), Path("data/README.md")}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".ps1", ".svg", ".gitignore", ".gitattributes"}
PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\\\s]+", re.I),
    re.compile(r"/Users/[^/\s]+", re.I),
    re.compile(r"/home/[^/\s]+", re.I),
    re.compile(r"OneDrive[/\\\\]", re.I),
]


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        yield path


def main() -> int:
    errors: list[str] = []
    checked = 0
    for path in iter_files():
        checked += 1
        rel = path.relative_to(ROOT)
        rel_lower = str(rel).casefold()
        if rel.parts and rel.parts[0] == "data" and rel not in ALLOWED_DATA:
            errors.append(f"Runtime data must not be committed: {rel}")
        if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            errors.append(f"Forbidden public file type: {rel}")
        if any(part in path.name.casefold() for part in FORBIDDEN_NAME_PARTS) and rel.parts[0] not in {"tools", "docs"}:
            errors.append(f"Likely generated/private filename: {rel}")
        if path.stat().st_size > 5 * 1024 * 1024:
            errors.append(f"Unexpected file larger than 5 MB: {rel}")
        if path.suffix.casefold() in TEXT_SUFFIXES or path.name in {".gitignore", ".gitattributes"}:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"Text file is not valid UTF-8: {rel}")
                continue
            if rel != Path("tools/public_release_audit.py"):
                for pattern in PATH_PATTERNS:
                    if pattern.search(text):
                        errors.append(f"Local user path found in {rel}: {pattern.pattern}")
    sample = ROOT / "sample_data" / "example_profile.json"
    if not sample.exists():
        errors.append("Synthetic sample profile is missing")
    else:
        try:
            data = json.loads(sample.read_text(encoding="utf-8"))
            if data.get("player", {}).get("player_id"):
                errors.append("Synthetic sample profile must not contain a player ID")
            if not data.get("sources", {}).get("sample", {}).get("synthetic"):
                errors.append("Synthetic sample profile is not clearly marked synthetic")
        except Exception as exc:
            errors.append(f"Sample profile could not be parsed: {exc}")

    if errors:
        print("PUBLIC RELEASE AUDIT FAILED")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1
    print(json.dumps({"status": "OK", "files_checked": checked, "root": str(ROOT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
