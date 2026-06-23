"""Persist and restore the active profile across browser sessions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .runtime_paths import data_dir, profiles_dir

ACTIVE_PROFILE_FILE = "active_profile.json"


def active_profile_path() -> Path:
    return data_dir() / ACTIVE_PROFILE_FILE


def read_active_profile_name() -> Optional[str]:
    path = active_profile_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    name = str(payload.get("name") or "").strip()
    return name or None


def remember_active_profile(name: str) -> None:
    clean = str(name or "").strip()
    if not clean:
        return
    path = active_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"name": clean}, indent=2), encoding="utf-8")
    temp.replace(path)


def load_startup_profile(
    *,
    default_profile: Callable[[], Dict[str, Any]],
    load_profile: Callable[[str], Dict[str, Any]],
    safe_profile_filename: Callable[[str], str],
) -> Dict[str, Any]:
    """Load the last saved profile from disk, or return a fresh default."""
    active_name = read_active_profile_name()
    if active_name:
        profile_path = profiles_dir() / f"{safe_profile_filename(active_name)}.json"
        if profile_path.exists():
            try:
                return load_profile(active_name)
            except (OSError, json.JSONDecodeError, ValueError):
                pass
    profiles = sorted(profiles_dir().glob("*.json"))
    if len(profiles) == 1:
        try:
            return load_profile(profiles[0].stem)
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return default_profile()
