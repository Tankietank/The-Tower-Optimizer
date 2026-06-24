import json

import pytest

from tower_optimizer.profile_session import (
    load_startup_profile,
    read_active_profile_name,
    remember_active_profile,
)
from tower_optimizer.runtime_paths import data_dir


@pytest.fixture(autouse=True)
def _clear_data_dir_cache():
    data_dir.cache_clear()
    yield
    data_dir.cache_clear()


def test_remember_and_read_active_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("TOWER_OPTIMIZER_DATA_DIR", str(tmp_path))
    (tmp_path / "profiles").mkdir()
    remember_active_profile("Tankie")
    assert read_active_profile_name() == "Tankie"


def test_load_startup_profile_prefers_active(tmp_path, monkeypatch):
    monkeypatch.setenv("TOWER_OPTIMIZER_DATA_DIR", str(tmp_path))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "Tankie.json").write_text(json.dumps({"name": "Tankie", "resources": {"coins": 1}}), encoding="utf-8")
    remember_active_profile("Tankie")

    loaded = load_startup_profile(
        default_profile=lambda: {"name": "default"},
        load_profile=lambda name: json.loads((profiles / f"{name}.json").read_text(encoding="utf-8")),
        safe_profile_filename=lambda name: name,
    )
    assert loaded["name"] == "Tankie"


def test_load_startup_profile_single_profile_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("TOWER_OPTIMIZER_DATA_DIR", str(tmp_path))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "OnlyOne.json").write_text(json.dumps({"name": "OnlyOne"}), encoding="utf-8")

    loaded = load_startup_profile(
        default_profile=lambda: {"name": "default"},
        load_profile=lambda name: json.loads((profiles / f"{name}.json").read_text(encoding="utf-8")),
        safe_profile_filename=lambda name: name,
    )
    assert loaded["name"] == "OnlyOne"
