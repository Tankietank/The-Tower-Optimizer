import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_release_audit():
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "public_release_audit.py")], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_sample_profile_is_synthetic():
    data = json.loads((ROOT / "sample_data" / "example_profile.json").read_text(encoding="utf-8"))
    assert data["name"] == "Synthetic Demo"
    assert data["player"]["player_id"] == ""
    assert data["sources"]["sample"]["synthetic"] is True
