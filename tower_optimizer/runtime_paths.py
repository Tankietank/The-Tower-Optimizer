"""Runtime filesystem locations for Tower Optimizer user data."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def data_dir() -> Path:
    override = os.environ.get("TOWER_OPTIMIZER_DATA_DIR", "").strip()
    return Path(override).expanduser() if override else Path("data")


def profiles_dir() -> Path:
    return data_dir() / "profiles"


def custom_icons_dir() -> Path:
    override = os.environ.get("TOWER_CUSTOM_ICON_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return data_dir() / "custom_icons"


def game_updates_dir() -> Path:
    return data_dir() / "game_updates"
