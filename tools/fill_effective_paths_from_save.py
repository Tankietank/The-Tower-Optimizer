"""Fill Effective Paths from playerInfo.dat and validate native engine output."""
from __future__ import annotations

import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EP = ROOT / "validation_fixtures" / "source_workbooks" / "The Tower" / "Effective Paths v5.06.04.00.xlsx"
OUT_DIR = ROOT / "validation_fixtures" / "dabes_validation"
DEFAULT_DOWNLOADS = Path.home() / "Downloads"

def _default_profile(name: str) -> Dict[str, Any]:
    sample = json.loads((ROOT / "sample_data" / "example_profile.json").read_text(encoding="utf-8"))
    profile = deepcopy(sample)
    profile["name"] = name
    return profile


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    quick = "--quick" in sys.argv or "-q" in sys.argv
    save_path = Path(args[0]) if args else Path(r"C:\Users\dabes\Downloads\playerInfo.dat")
    ep_source = Path(args[1]) if len(args) > 1 else DEFAULT_EP
    if not save_path.exists():
        print(f"Save not found: {save_path}")
        return 1
    if not ep_source.exists():
        print(f"Effective Paths workbook not found: {ep_source}")
        return 1

    sys.path.insert(0, str(ROOT))
    from openpyxl import load_workbook

    from tower_optimizer.calibration import build_calibration_report, build_native_paths
    from tower_optimizer.ep_master_sheet import read_master_sheet_profile
    from tower_optimizer.ep_xlsx_patch import fill_effective_paths_workbook
    from tower_optimizer.roi_reference import parse_effective_paths_roi_reference_bytes
    from tower_optimizer.save_parser import apply_player_save_patch, build_profile_patch, decode_player_save_file

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_xlsx = OUT_DIR / "Effective Paths v5.06.04.00 - dabes filled.xlsx"
    out_profile = OUT_DIR / "dabes_profile.json"
    patch = build_profile_patch(decode_player_save_file(save_path))
    profile = _default_profile("dabes")
    apply_player_save_patch(profile, patch, replace=True, import_battle_history=True, source_name=save_path.name)
    out_profile.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    stats = fill_effective_paths_workbook(ep_source, out_xlsx, profile)

    downloads_copy = DEFAULT_DOWNLOADS / out_xlsx.name
    try:
        shutil.copy2(out_xlsx, downloads_copy)
    except OSError:
        downloads_copy = None

    if quick:
        print("\n=== Lazy fill complete ===")
        print(f"  Filled EP: {out_xlsx}")
        if downloads_copy:
            print(f"  Downloads: {downloads_copy}")
        print(f"  Profile:   {out_profile}")
        print("\n1. Open the Downloads copy in Excel")
        print("2. Wait for recalc (Ctrl+Alt+F9), then Save")
        print("3. Tower Optimizer -> Import playerInfo.dat + Import ROI Reference")
        return 0

    read_back = read_master_sheet_profile(load_workbook(out_xlsx, data_only=True)["Master Sheet"])
    round_trip_ok = True
    for section in ("labs", "workshop", "enhancements"):
        source = profile.get(section) or {}
        mirrored = read_back.get(section) or {}
        missing = [name for name in source if name not in mirrored]
        mismatched = [
            name for name in source
            if name in mirrored and int(mirrored[name]) != int(source[name])
        ]
        if missing or mismatched:
            round_trip_ok = False
        print(f"Round-trip {section}: wrote {stats[section]}, read {len(mirrored)}, missing {len(missing)}, mismatched {len(mismatched)}")

    native = build_native_paths(profile, steps=10)
    print("\n=== Native engine top picks (your save profile) ===")
    for path_key, rows in sorted(native.items()):
        if not rows:
            continue
        top = rows[0]
        print(f"  {path_key}: {top.get('Upgrade')} (ROI {top.get('ROI Numeric', top.get('ROI'))})")

    # Existing cached ROI paths in template (stale until workbook is recalculated)
    ref = parse_effective_paths_roi_reference_bytes(out_xlsx.read_bytes(), filename=out_xlsx.name)
    profile["roi_reference"] = ref
    report = build_calibration_report(profile, steps=10)
    print("\n=== Calibration vs cached EP paths (template may be stale) ===")
    print(f"  Overall: {report.get('overall')} | Agreement: {report.get('overall_agreement_percent')}%")
    print(f"  Counts: {report.get('counts')}")
    for row in report.get("summary", []):
        print(
            f"  {row.get('Status'):12} {row.get('Path'):18} "
            f"native={row.get('Native Top')} | ref={row.get('Reference Top')}"
        )

    print("\n=== Output files ===")
    print(f"  Profile JSON: {out_profile}")
    print(f"  Filled EP:      {out_xlsx}")
    if downloads_copy:
        print(f"  Downloads copy: {downloads_copy}")
    print("\nNext: open the filled EP workbook in Google Sheets or Excel, wait for formulas to recalculate,")
    print("save it, then Import / Export -> ROI Reference in Tower Optimizer and open Calibration Center.")

    return 0 if round_trip_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
