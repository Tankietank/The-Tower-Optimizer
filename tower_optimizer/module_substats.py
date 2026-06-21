from __future__ import annotations

from typing import Any, Dict, List


def format_substat_line(sub: Any) -> str:
    if isinstance(sub, str):
        return sub.strip()
    if not isinstance(sub, dict):
        return str(sub).strip()
    label = str(sub.get("display") or sub.get("name") or "Unnamed").strip()
    rarity = str(sub.get("rarity") or "").strip()
    value = sub.get("value")
    parts = [label]
    if rarity and rarity.lower() not in {"none", "unknown"}:
        parts.append(f"({rarity})")
    if value not in (None, ""):
        parts.append(f"= {value}")
    if sub.get("locked"):
        parts.append("[locked]")
    return " ".join(parts).strip()


def format_substats_for_editor(substats: Any) -> str:
    if not isinstance(substats, list):
        return str(substats or "")
    return "\n".join(line for line in (format_substat_line(item) for item in substats) if line)


def parse_substats_from_editor(text: str, previous: Any = None) -> List[Dict[str, Any]]:
    previous_list = previous if isinstance(previous, list) else []
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    parsed: List[Dict[str, Any]] = []
    for index, line in enumerate(lines):
        if index < len(previous_list) and isinstance(previous_list[index], dict):
            merged = dict(previous_list[index])
            merged["display"] = line
            if not merged.get("name"):
                merged["name"] = line.split("(")[0].strip() if "(" in line else line
            parsed.append(merged)
        else:
            parsed.append({"name": line, "display": line})
    return parsed
