"""Generate bundled module icon SVGs for save import / visual pages."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "tower_optimizer" / "game_data" / "modules.json"
OUT = ROOT / "assets" / "modules"

SLOT_STYLE = {
    "Cannon": ("#ff6b6b", "#ffd166"),
    "Armor": ("#4dabf7", "#d0ebff"),
    "Generator": ("#69db7c", "#d3f9d8"),
    "Core": ("#b197fc", "#e5dbff"),
}


def slug(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-").replace("--", "-")


def initials(name: str) -> str:
    parts = [part for part in name.replace("-", " ").split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def svg_for(name: str, slot: str) -> str:
    primary, accent = SLOT_STYLE.get(slot, ("#868e96", "#dee2e6"))
    label = initials(name)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{primary}"/>
      <stop offset="100%" stop-color="{accent}"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="168" height="168" rx="28" fill="#101729" stroke="url(#g)" stroke-width="8"/>
  <path d="M100 42 L148 72 V128 L100 158 L52 128 V72 Z" fill="url(#g)" opacity="0.25"/>
  <text x="100" y="112" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="44" font-weight="700" fill="#f8f9fa">{label}</text>
  <text x="100" y="170" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="{accent}">{slot[:1]}</text>
</svg>
"""


def main() -> None:
    payload = json.loads(MODULES.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    count = 0
    for slot, names in payload.get("slots", {}).items():
        for name in names:
            if not name:
                continue
            path = OUT / f"{slug(name)}.svg"
            path.write_text(svg_for(name, slot), encoding="utf-8")
            count += 1
    print(f"Wrote {count} module icons to {OUT}")


if __name__ == "__main__":
    main()
