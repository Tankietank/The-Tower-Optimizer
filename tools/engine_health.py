from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tower_optimizer.regression import run_engine_health

parser = argparse.ArgumentParser(description="Run Tower Optimizer standalone engine health checks.")
parser.add_argument("--profile", help="Profile JSON path. Defaults to the first profile in data/profiles.")
parser.add_argument("--output", help="Optional JSON output path.")
args = parser.parse_args()

if args.profile:
    profile_path = Path(args.profile)
else:
    profiles = sorted((ROOT / "data" / "profiles").glob("*.json"))
    if not profiles:
        raise SystemExit("No profile JSON found. Supply --profile PATH.")
    profile_path = profiles[0]

profile = json.loads(profile_path.read_text(encoding="utf-8"))
report = run_engine_health(profile, steps=10)
print(json.dumps(report, indent=2))
if args.output:
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
raise SystemExit(1 if report.get("overall") == "FAIL" else 0)
