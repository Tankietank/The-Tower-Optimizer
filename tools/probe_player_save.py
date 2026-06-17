"""Inspect a local The Tower playerInfo.dat save without modifying it.

Usage:
    python tools/probe_player_save.py data/imports/save_probe/playerInfo.dat
    python tools/probe_player_save.py path/to/playerInfo.dat --json-out data/imports/save_probe/decoded_preview.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NRBF_SIGNATURE = 0x00010000


def read_header(payload: bytes) -> dict:
    if len(payload) < 32:
        raise ValueError(f"File too small ({len(payload)} bytes).")
    root_id = struct.unpack_from("<I", payload, 0)[0]
    header_length = struct.unpack_from("<I", payload, 4)[0]
    major = payload[8]
    minor = payload[9]
    return {
        "root_id": root_id,
        "header_length": header_length,
        "major_version": major,
        "minor_version": minor,
        "looks_like_nrbf": root_id == NRBF_SIGNATURE,
        "raw_prefix_hex": payload[:64].hex(),
    }


def load_bytes(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw), "gzip+nrbf"
    if len(raw) >= 4 and struct.unpack_from("<I", raw, 0)[0] == NRBF_SIGNATURE:
        return raw, "nrbf"
    return raw, "unknown"


def summarize_binary(payload: bytes) -> dict:
    header = read_header(payload)
    printable = sum(1 for b in payload if 32 <= b <= 126)
    return {
        **header,
        "decompressed_size": len(payload),
        "printable_ratio": round(printable / max(len(payload), 1), 4),
        "contains_workshop": b"upgradeWorkshop" in payload or b"Workshop" in payload,
        "contains_research": b"researchLevel" in payload or b"Research" in payload,
        "contains_modules": b"Module" in payload or b"module" in payload,
        "contains_cards": b"Card" in payload or b"card" in payload,
        "contains_relics": b"Relic" in payload or b"relic" in payload,
        "contains_uw": b"Ultimate" in payload or b"ultimate" in payload,
    }


def extract_ascii_strings(payload: bytes, min_len: int = 4) -> list[str]:
    current: list[str] = []
    strings: list[str] = []
    for byte in payload:
        if 32 <= byte <= 126:
            current.append(chr(byte))
        else:
            if len(current) >= min_len:
                strings.append("".join(current))
            current = []
    if len(current) >= min_len:
        strings.append("".join(current))
    # De-dupe while preserving order; cap output size.
    seen: set[str] = set()
    unique: list[str] = []
    for item in strings:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique[:500]


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a playerInfo.dat save file.")
    parser.add_argument("path", type=Path, help="Path to playerInfo.dat")
    parser.add_argument("--json-out", type=Path, help="Optional path for a redacted analysis JSON")
    args = parser.parse_args()

    path = args.path.resolve()
    if not path.exists():
        print(f"File not found: {path}")
        return 1

    payload, container = load_bytes(path)
    summary = summarize_binary(payload)
    strings = extract_ascii_strings(payload)
    decoded = None
    decode_error = None
    try:
        import nrbf

        decoded = nrbf.loads(payload)
    except Exception as exc:
        decode_error = str(exc)

    report = {
        "source_file": str(path),
        "container": container,
        "summary": summary,
        "interesting_strings": [
            s for s in strings
            if any(token in s for token in (
                "Workshop", "Research", "Module", "Card", "Relic", "Ultimate",
                "Golden", "Black Hole", "Death Wave", "Guardian", "Bot", "Vault",
                "Coin", "Stone", "Gem", "Player", "Tier", "Wave",
            ))
        ][:200],
        "sample_strings": strings[:100],
        "next_step": (
            "NRBF decode succeeded; use tower_optimizer.save_parser to build a profile patch."
            if isinstance(decoded, dict)
            else (
                f"NRBF decode failed: {decode_error}"
                if decode_error
                else (
                    "NRBF header detected. Full decode requires the nrbf package."
                    if summary.get("looks_like_nrbf")
                    else "Unknown container; share the file path so we can inspect further."
                )
            )
        ),
    }
    if isinstance(decoded, dict):
        from tower_optimizer.save_parser import build_profile_patch

        patch = build_profile_patch(decoded)
        report["profile_patch_sections"] = {
            key: len(value) if isinstance(value, dict) else 1
            for key, value in patch.items()
            if value
        }

    print(json.dumps(report, indent=2))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote analysis to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
