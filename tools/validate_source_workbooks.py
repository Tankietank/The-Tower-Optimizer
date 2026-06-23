"""Compare bundled engine data against supplied Tower workbooks."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EP = ROOT / "validation_fixtures" / "source_workbooks" / "The Tower" / "Effective Paths v5.06.04.00.xlsx"


class _Upload:
    def __init__(self, path: Path) -> None:
        self.name = path.name
        self._payload = path.read_bytes()

    def getvalue(self) -> bytes:
        return self._payload


def main() -> int:
    ep_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EP
    if not ep_path.exists():
        print(f"Effective Paths workbook not found: {ep_path}")
        return 1

    sys.path.insert(0, str(ROOT))
    from tower_optimizer.calibration import build_calibration_report
    from tower_optimizer.engines.core import LAB_MAX_LEVELS, WORKSHOP_MAX_LEVELS
    from tower_optimizer.reliability import SUPPORTED_WORKBOOK_VERSIONS, compare_cap_maps, extract_effective_paths_caps
    from tower_optimizer.roi_reference import parse_effective_paths_roi_reference_bytes

    payload = ep_path.read_bytes()
    caps = extract_effective_paths_caps(payload)
    workshop_diff = compare_cap_maps(WORKSHOP_MAX_LEVELS, caps["workshop"])
    lab_diff = compare_cap_maps(LAB_MAX_LEVELS, caps["labs"])

    print("=== Bundled workbook versions ===")
    for key, value in sorted(SUPPORTED_WORKBOOK_VERSIONS.items()):
        print(f"  {key}: {value}")

    print("\n=== Cap parity (_IDS vs bundled) ===")
    print(f"  Workshop differences: {len(workshop_diff)}")
    for row in workshop_diff[:15]:
        print(f"    {row['Entry']}: embedded={row['Embedded maximum']} uploaded={row['Uploaded maximum']} ({row['Change']})")
    if len(workshop_diff) > 15:
        print(f"    ... and {len(workshop_diff) - 15} more")
    print(f"  Lab differences: {len(lab_diff)}")
    for row in lab_diff[:15]:
        print(f"    {row['Entry']}: embedded={row['Embedded maximum']} uploaded={row['Uploaded maximum']} ({row['Change']})")
    if len(lab_diff) > 15:
        print(f"    ... and {len(lab_diff) - 15} more")

    ref = parse_effective_paths_roi_reference_bytes(payload, filename=ep_path.name)
    nonempty = sum(1 for path in ref["paths"].values() if path.get("rows"))
    print("\n=== ROI reference import ===")
    print(f"  Version: {ref['source'].get('effective_paths_version')}")
    print(f"  Paths with rows: {nonempty}/{len(ref['paths'])}")
    for warning in ref.get("warnings", []):
        print(f"  WARN: {warning}")

    profile_path = ROOT / "sample_data" / "example_profile.json"
    profile: Dict[str, Any] = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["roi_reference"] = ref
    report = build_calibration_report(profile, steps=15)

    print("\n=== Calibration vs synthetic demo profile ===")
    print(f"  Overall: {report.get('overall')}")
    print(f"  Agreement: {report.get('overall_agreement_percent')}%")
    print(f"  Counts: {report.get('counts')}")
    for row in report.get("summary", []):
        status = row.get("Status")
        marker = "!!" if status == "Different" else "ok" if status in {"Exact", "Close"} else "--"
        print(
            f"  {marker} {row.get('Path')}: {status} | "
            f"native={row.get('Native Top')} ref={row.get('Reference Top')} | "
            f"agreement={row.get('Weighted Agreement %')}%"
        )

    different = [row for row in report.get("summary", []) if row.get("Status") == "Different"]
    if workshop_diff or lab_diff or different:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
