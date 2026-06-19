from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .reliability import (
    SUPPORTED_WORKBOOK_VERSIONS,
    compare_cap_maps,
    extract_effective_paths_caps,
    parse_version,
    workbook_compatibility,
)

from .runtime_paths import game_updates_dir

UPDATE_SCHEMA_VERSION = "1.0"
DEFAULT_UPDATE_ROOT = game_updates_dir()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[Path] = None) -> Path:
    return Path(root) if root is not None else DEFAULT_UPDATE_ROOT


def _active_path(root: Optional[Path] = None) -> Path:
    return _root(root) / "active_update.json"


def _staging_dir(root: Optional[Path] = None) -> Path:
    return _root(root) / "staging"


def _history_dir(root: Optional[Path] = None) -> Path:
    return _root(root) / "history"


def _safe_write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return path


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in str(value)).strip("._") or "update"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _version_key(value: str) -> Tuple[int, ...]:
    return parse_version(value) or (0,)


def _normalize_caps(values: Mapping[str, Any]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for name, maximum in values.items():
        try:
            result[str(name)] = int(maximum)
        except (TypeError, ValueError):
            continue
    return result


def get_active_update(root: Optional[Path] = None) -> Dict[str, Any]:
    path = _active_path(root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_runtime_overlay(root: Optional[Path] = None) -> Dict[str, Any]:
    """Load the approved local metadata overlay without mutating package files."""
    payload = get_active_update(root)
    if not payload or payload.get("schema_version") != UPDATE_SCHEMA_VERSION:
        return {}
    result = dict(payload)
    result["workshop_max_levels"] = _normalize_caps(payload.get("workshop_max_levels", {}))
    result["lab_max_levels"] = _normalize_caps(payload.get("lab_max_levels", {}))
    versions = payload.get("workbook_versions", {})
    result["workbook_versions"] = {str(key): str(value) for key, value in versions.items()} if isinstance(versions, dict) else {}
    return result


def _richer_changes(current: Mapping[str, int], incoming: Mapping[str, int]) -> List[Dict[str, Any]]:
    rows = compare_cap_maps(current, incoming)
    for row in rows:
        old = row.get("Embedded maximum")
        new = row.get("Uploaded maximum")
        if old is None:
            row["Direction"] = "Added"
            row["Delta"] = new
        elif new is None:
            row["Direction"] = "Removed"
            row["Delta"] = None
        else:
            delta = int(new) - int(old)
            row["Delta"] = delta
            row["Direction"] = "Increased" if delta > 0 else "Decreased"
    return rows


def _coverage(incoming: Mapping[str, int], baseline: Mapping[str, int]) -> float:
    if not baseline:
        return 100.0
    return round(100.0 * len(set(incoming) & set(baseline)) / len(baseline), 1)


def analyze_update_bundle(
    files: Sequence[Tuple[str, bytes]],
    baseline_workshop: Mapping[str, int],
    baseline_labs: Mapping[str, int],
    supported_versions: Optional[Mapping[str, str]] = None,
    app_version: str = "unknown",
) -> Dict[str, Any]:
    """Inspect a workbook bundle and build a reviewable metadata update candidate.

    This workflow intentionally updates only maximum-level metadata and recognized
    workbook versions. Formula curves and cost tables remain code-reviewed release
    data and are never overwritten automatically.
    """
    supported = dict(supported_versions or SUPPORTED_WORKBOOK_VERSIONS)
    baseline_workshop = _normalize_caps(baseline_workshop)
    baseline_labs = _normalize_caps(baseline_labs)
    analyzed_at = utc_now()
    file_rows: List[Dict[str, Any]] = []
    payload_by_kind: Dict[str, List[Tuple[str, bytes, Dict[str, Any]]]] = {}

    for filename, raw_payload in files:
        payload = bytes(raw_payload)
        info = workbook_compatibility(filename, payload)
        row = {
            "File": filename,
            "Type": info.get("kind", "Unknown"),
            "Version": info.get("version") or "",
            "Supported version": info.get("supported_version") or supported.get(str(info.get("kind")), ""),
            "Compatibility": info.get("status", "Unknown"),
            "Sheets": info.get("sheets", 0),
            "Size KB": round(len(payload) / 1024, 1),
            "SHA256": sha256_bytes(payload),
            "Has EXPORT": bool(info.get("has_export")),
            "Has _IDS": bool(info.get("has_private_ids")),
            "Error": info.get("error", ""),
        }
        file_rows.append(row)
        payload_by_kind.setdefault(str(row["Type"]), []).append((filename, payload, info))

    duplicates = sorted(kind for kind, entries in payload_by_kind.items() if kind != "Unknown" and len(entries) > 1)
    recognized = sorted(kind for kind in payload_by_kind if kind != "Unknown")
    missing_expected = sorted(set(supported) - set(recognized))
    workbook_versions: Dict[str, str] = dict(supported)
    for row in file_rows:
        if row["Type"] != "Unknown" and row["Version"]:
            workbook_versions[str(row["Type"])] = str(row["Version"])

    workshop_target = dict(baseline_workshop)
    labs_target = dict(baseline_labs)
    workshop_changes: List[Dict[str, Any]] = []
    lab_changes: List[Dict[str, Any]] = []
    effective_paths_version = supported.get("Effective Paths", "")
    effective_paths_filename = ""
    extraction_error = ""
    workshop_coverage = 100.0
    lab_coverage = 100.0

    effective_entries = payload_by_kind.get("Effective Paths", [])
    if effective_entries:
        effective_entries = sorted(effective_entries, key=lambda item: _version_key(item[2].get("version", "")), reverse=True)
        effective_paths_filename, effective_payload, effective_info = effective_entries[0]
        effective_paths_version = str(effective_info.get("version") or effective_paths_version)
        try:
            caps = extract_effective_paths_caps(effective_payload)
            incoming_workshop = _normalize_caps(caps.get("workshop", {}))
            incoming_labs = _normalize_caps(caps.get("labs", {}))
            workshop_coverage = _coverage(incoming_workshop, baseline_workshop)
            lab_coverage = _coverage(incoming_labs, baseline_labs)
            if incoming_workshop:
                workshop_target = incoming_workshop
            if incoming_labs:
                labs_target = incoming_labs
            workshop_changes = _richer_changes(baseline_workshop, workshop_target)
            lab_changes = _richer_changes(baseline_labs, labs_target)
        except Exception as exc:
            extraction_error = str(exc)

    errors = [row for row in file_rows if row.get("Error")]
    blocked_reasons: List[str] = []
    review_reasons: List[str] = []
    info_notes: List[str] = []

    if not files:
        blocked_reasons.append("No workbook files were supplied.")
    if errors:
        blocked_reasons.append(f"{len(errors)} workbook(s) could not be opened.")
    if duplicates:
        blocked_reasons.append("Duplicate recognized workbook types were supplied: " + ", ".join(duplicates))
    if extraction_error:
        blocked_reasons.append("Effective Paths metadata extraction failed: " + extraction_error)
    if effective_entries and (workshop_coverage < 90.0 or lab_coverage < 90.0):
        blocked_reasons.append(
            f"Effective Paths coverage is incomplete (Workshop {workshop_coverage}%, Labs {lab_coverage}%)."
        )
    if any(row.get("Direction") == "Removed" for row in workshop_changes + lab_changes):
        blocked_reasons.append("The upload omits entries that exist in the current metadata.")

    newer = [row for row in file_rows if row.get("Compatibility") == "Newer than supported"]
    older = [row for row in file_rows if row.get("Compatibility") == "Older than supported"]
    decreases = [row for row in workshop_changes + lab_changes if row.get("Direction") == "Decreased"]
    if newer:
        review_reasons.append(f"{len(newer)} workbook(s) are newer than the versions bundled with this release.")
    if older:
        review_reasons.append(f"{len(older)} workbook(s) are older than the versions bundled with this release.")
    if workshop_changes or lab_changes:
        review_reasons.append(
            f"Maximum-level metadata changes were found: {len(workshop_changes)} Workshop and {len(lab_changes)} Lab."
        )
    if decreases:
        review_reasons.append(f"{len(decreases)} maximum level(s) decrease and may change Gold Box status.")
    if missing_expected:
        info_notes.append(
            "This is a partial update bundle. Missing companion workbooks are left at their currently supported versions."
        )
    if not effective_entries:
        info_notes.append("No Effective Paths workbook was supplied, so maximum-level metadata is unchanged.")
    info_notes.append("Engine formulas, value curves, and cost tables are never changed by this automatic workflow.")

    if blocked_reasons:
        risk_level = "BLOCKED"
        validation = "FAIL"
    elif review_reasons:
        risk_level = "REVIEW"
        validation = "WARN"
    else:
        risk_level = "SAFE"
        validation = "PASS"

    digest_seed = "|".join(sorted(row["SHA256"] for row in file_rows)) + analyzed_at
    update_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + hashlib.sha256(digest_seed.encode("utf-8")).hexdigest()[:8]
    candidate = {
        "schema_version": UPDATE_SCHEMA_VERSION,
        "update_id": update_id,
        "created_at": analyzed_at,
        "created_with_app": app_version,
        "risk_level": risk_level,
        "validation": validation,
        "effective_paths_version": effective_paths_version,
        "effective_paths_filename": effective_paths_filename,
        "workbook_versions": workbook_versions,
        "workshop_max_levels": workshop_target,
        "lab_max_levels": labs_target,
        "changes": {
            "workshop": workshop_changes,
            "labs": lab_changes,
        },
        "source_files": [
            {
                "filename": row["File"],
                "kind": row["Type"],
                "version": row["Version"],
                "sha256": row["SHA256"],
                "size_kb": row["Size KB"],
            }
            for row in file_rows
        ],
        "scope": ["recognized workbook versions", "Workshop maximum levels", "Lab maximum levels"],
        "formula_tables_updated": False,
        "restart_required": True,
        "blocked_reasons": blocked_reasons,
        "review_reasons": review_reasons,
        "notes": info_notes,
    }
    return {
        "schema_version": UPDATE_SCHEMA_VERSION,
        "analyzed_at": analyzed_at,
        "app_version": app_version,
        "validation": validation,
        "risk_level": risk_level,
        "files": file_rows,
        "recognized_types": recognized,
        "missing_expected": missing_expected,
        "duplicates": duplicates,
        "coverage": {"Workshop %": workshop_coverage, "Labs %": lab_coverage},
        "workshop_changes": workshop_changes,
        "lab_changes": lab_changes,
        "blocked_reasons": blocked_reasons,
        "review_reasons": review_reasons,
        "notes": info_notes,
        "candidate": candidate,
    }


def stage_update_candidate(candidate: Mapping[str, Any], root: Optional[Path] = None) -> Path:
    if candidate.get("validation") == "FAIL" or candidate.get("risk_level") == "BLOCKED":
        raise ValueError("Blocked update candidates cannot be staged.")
    update_id = _safe_id(str(candidate.get("update_id") or datetime.now().strftime("%Y%m%d_%H%M%S")))
    payload = dict(candidate)
    payload["staged_at"] = utc_now()
    return _safe_write_json(_staging_dir(root) / f"{update_id}.json", payload)


def _archive_active(root: Optional[Path], reason: str) -> Optional[Path]:
    active_path = _active_path(root)
    if not active_path.exists():
        return None
    payload = get_active_update(root)
    update_id = _safe_id(str(payload.get("update_id") or "unknown"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = _history_dir(root) / f"{stamp}__{update_id}__{_safe_id(reason)}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(active_path, destination)
    return destination


def apply_update_candidate(
    candidate: Mapping[str, Any],
    root: Optional[Path] = None,
    allow_review: bool = False,
) -> Path:
    validation = str(candidate.get("validation", ""))
    risk = str(candidate.get("risk_level", ""))
    if validation == "FAIL" or risk == "BLOCKED":
        raise ValueError("This update candidate is blocked and cannot be applied.")
    if risk == "REVIEW" and not allow_review:
        raise ValueError("This update requires explicit review confirmation before it can be applied.")
    workshop = _normalize_caps(candidate.get("workshop_max_levels", {}))
    labs = _normalize_caps(candidate.get("lab_max_levels", {}))
    if not workshop or not labs:
        raise ValueError("A complete Workshop and Lab metadata map is required before applying an update.")

    _archive_active(root, reason="superseded")
    payload = dict(candidate)
    payload["schema_version"] = UPDATE_SCHEMA_VERSION
    payload["applied_at"] = utc_now()
    payload["status"] = "ACTIVE"
    payload["workshop_max_levels"] = workshop
    payload["lab_max_levels"] = labs
    path = _safe_write_json(_active_path(root), payload)

    # Preserve an immutable history copy of every applied update.
    history_path = _history_dir(root) / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}__{_safe_id(str(payload.get('update_id')))}__applied.json"
    _safe_write_json(history_path, payload)
    return path


def rollback_active_update(root: Optional[Path] = None) -> Optional[Path]:
    active_path = _active_path(root)
    if not active_path.exists():
        return None
    archived = _archive_active(root, reason="rolled_back")
    active_path.unlink()
    return archived


def list_update_history(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    directory = _history_dir(root)
    if not directory.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        rows.append({
            "File": path.name,
            "Update ID": payload.get("update_id", "Unknown"),
            "Effective Paths": payload.get("effective_paths_version", "Unknown"),
            "Risk": payload.get("risk_level", "Unknown"),
            "Applied": payload.get("applied_at", ""),
            "Size KB": round(path.stat().st_size / 1024, 1),
        })
    return rows


def active_update_health(root: Optional[Path] = None) -> Dict[str, Any]:
    path = _active_path(root)
    if not path.exists():
        return {
            "Component": "Local game-data overlay",
            "Status": "INFO",
            "Detail": "No local overlay is active; bundled metadata is in use.",
            "Suggested Action": "—",
        }
    try:
        payload = load_runtime_overlay(root)
        if not payload.get("workshop_max_levels") or not payload.get("lab_max_levels"):
            raise ValueError("Active overlay is missing complete maximum-level maps.")
        return {
            "Component": "Local game-data overlay",
            "Status": "PASS",
            "Detail": f"{payload.get('update_id', 'update')} · Effective Paths {payload.get('effective_paths_version', 'Unknown')}",
            "Suggested Action": "Restart Streamlit after applying or rolling back an overlay.",
        }
    except Exception as exc:
        return {
            "Component": "Local game-data overlay",
            "Status": "FAIL",
            "Detail": str(exc),
            "Suggested Action": "Roll back the active update from System & Updates.",
        }


def _csv_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    rows = list(rows)
    if not rows:
        return b""
    output = io.StringIO()
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(str(key))
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))
    return output.getvalue().encode("utf-8-sig")


def export_update_bundle(report: Mapping[str, Any]) -> bytes:
    buffer = io.BytesIO()
    candidate = report.get("candidate", {})
    readme = """Tower Optimizer game-data update candidate\n\nThis package contains a review manifest and metadata patch only. It does not contain the uploaded workbooks and it does not modify engine formulas, cost curves, or value tables. Apply the candidate through System & Updates after reviewing every warning. A full Streamlit restart is required after apply or rollback.\n"""
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", readme)
        archive.writestr("analysis_report.json", json.dumps(dict(report), indent=2, ensure_ascii=False, default=str))
        archive.writestr("active_update_candidate.json", json.dumps(candidate, indent=2, ensure_ascii=False, default=str))
        archive.writestr("files.csv", _csv_bytes(report.get("files", [])))
        archive.writestr("workshop_changes.csv", _csv_bytes(report.get("workshop_changes", [])))
        archive.writestr("lab_changes.csv", _csv_bytes(report.get("lab_changes", [])))
    return buffer.getvalue()
