"""Custom icon discovery, validation, import, and export for Tower Optimizer.

Default artwork ships under ``assets``. User-supplied artwork is stored under
``data/custom_icons`` so application upgrades do not overwrite it.
"""
from __future__ import annotations

import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import unquote

from .runtime_paths import custom_icons_dir as _custom_icons_dir

ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets"
GAME_DATA_ROOT = Path(__file__).resolve().parent / "game_data"
TOWERSMITH_ICON_PATHS_FILE = GAME_DATA_ROOT / "towersmith_icon_paths.json"
SUPPORTED_EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg", ".svg")
MODULE_SLOT_FOLDERS = {
    "cannon": "cannon",
    "armor": "armor",
    "generator": "generator",
    "core": "core",
}
RELIC_RARITY_FOLDERS = {
    "1-rare": "rare",
    "2-epic": "epic",
    "3-legendary": "legendary",
    "rare": "rare",
    "epic": "epic",
    "legendary": "legendary",
}
UPLOAD_EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg")
MAX_ICON_BYTES = 8 * 1024 * 1024
MAX_PACK_BYTES = 64 * 1024 * 1024

UW_NAME_TO_WORKSHOP_ID = {
    "Chain Lightning": "chainLightning",
    "Smart Missiles": "smartMissiles",
    "Death Wave": "deathWave",
    "Chrono Field": "chronoField",
    "Inner Land Mines": "innerLandMines",
    "Golden Tower": "goldenTower",
    "Poison Swamp": "poisonSwamp",
    "Black Hole": "blackHole",
    "Spotlight": "spotlight",
}

FIXED_ICON_SPECS: tuple[dict[str, str], ...] = (
    {"key": "brand/tower_optimizer", "label": "Tower Optimizer logo", "category": "Brand", "default": "brand/tower_optimizer.svg"},
    {"key": "resources/coins", "label": "Coins", "category": "Resources", "default": "resources/coins.svg"},
    {"key": "resources/stones", "label": "Stones", "category": "Resources", "default": "resources/stones.svg"},
    {"key": "resources/gems", "label": "Gems", "category": "Resources", "default": "resources/gems.svg"},
    {"key": "systems/cards", "label": "Cards", "category": "Systems", "default": "systems/cards.svg"},
    {"key": "systems/modules", "label": "Modules", "category": "Systems", "default": "systems/modules.svg"},
    {"key": "systems/relics", "label": "Relics", "category": "Systems", "default": "systems/relics.svg"},
    {"key": "ultimate_weapons/golden_tower", "label": "Golden Tower", "category": "Ultimate Weapons", "default": "ultimate_weapons/golden_tower.svg"},
    {"key": "ultimate_weapons/black_hole", "label": "Black Hole", "category": "Ultimate Weapons", "default": "ultimate_weapons/black_hole.svg"},
    {"key": "ultimate_weapons/death_wave", "label": "Death Wave", "category": "Ultimate Weapons", "default": "ultimate_weapons/death_wave.svg"},
    {"key": "placeholders/relic", "label": "Relic fallback", "category": "Fallbacks", "default": "placeholders/relic.svg"},
)


def custom_icon_root() -> Path:
    return _custom_icons_dir()


def configured_game_asset_roots() -> List[Path]:
    """Optional local artwork folders configured explicitly by the user."""
    roots: List[Path] = []
    seen: set[str] = set()
    for raw in (
        os.environ.get("TOWER_GAME_ASSETS_DIR", "").strip(),
        os.environ.get("TOWER_SMITH_PUBLIC_DIR", "").strip(),
    ):
        if not raw:
            continue
        path = Path(raw).expanduser()
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_dir():
            roots.append(path)
    return roots


def _first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for path in paths:
        if path.is_file():
            return path
    return None


def _decode_relative_path(relative: str) -> Path:
    parts = [unquote(part) for part in str(relative).replace("\\", "/").strip("/").split("/") if part]
    return Path(*parts)


@lru_cache(maxsize=1)
def _towersmith_icon_paths() -> Dict[str, Any]:
    if not TOWERSMITH_ICON_PATHS_FILE.is_file():
        return {}
    try:
        payload = json.loads(TOWERSMITH_ICON_PATHS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


@lru_cache(maxsize=1)
def _module_name_to_workshop_id() -> Dict[str, str]:
    mapping_path = GAME_DATA_ROOT / "save_mappings.json"
    if not mapping_path.is_file():
        return {}
    try:
        payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("module_workshop_id_to_name") if isinstance(payload, Mapping) else {}
    if not isinstance(rows, Mapping):
        return {}
    return {str(name).casefold(): str(workshop_id) for workshop_id, name in rows.items()}


@lru_cache(maxsize=1)
def _relic_name_to_catalog_id() -> Dict[str, str]:
    mapping_path = GAME_DATA_ROOT / "relics.json"
    if not mapping_path.is_file():
        return {}
    try:
        payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("by_index") if isinstance(payload, Mapping) else []
    if not isinstance(rows, list):
        return {}
    result: Dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").strip()
        relic_id = str(row.get("id") or "").strip()
        if name and relic_id:
            result[name.casefold()] = relic_id
    return result


def _module_slot_key(module_slot: str) -> str:
    return MODULE_SLOT_FOLDERS.get(_slug(module_slot), _slug(module_slot))


def _towersmith_mapped_relatives(
    category: str,
    name: str,
    *,
    relic_rarity: str = "",
    module_slot: str = "",
) -> Iterable[str]:
    payload = _towersmith_icon_paths()
    title = str(name).strip()
    if not title:
        return
    category_key = _slug(category).replace("-", "_")
    if category_key in {"modules", "module"}:
        slot = _module_slot_key(module_slot)
        workshop_id = _module_name_to_workshop_id().get(title.casefold(), "")
        if not workshop_id:
            return
        slot_map = payload.get("modules") if isinstance(payload.get("modules"), Mapping) else {}
        if slot and isinstance(slot_map.get(slot), Mapping):
            relative = slot_map[slot].get(workshop_id)
            if relative:
                yield f"modules/{relative}"
        for slot_name, modules in slot_map.items():
            if isinstance(modules, Mapping) and workshop_id in modules:
                yield f"modules/{modules[workshop_id]}"
                break
    elif category_key in {"relics", "relic"}:
        relic_id = _relic_name_to_catalog_id().get(title.casefold(), "")
        relic_map = payload.get("relics") if isinstance(payload.get("relics"), Mapping) else {}
        if relic_id and relic_id in relic_map:
            yield f"relics/{relic_map[relic_id]}"
    elif category_key in {"ultimate_weapons", "ultimate_weapon", "uw"}:
        weapon_id = UW_NAME_TO_WORKSHOP_ID.get(title)
        weapon_map = payload.get("ultimate_weapons") if isinstance(payload.get("ultimate_weapons"), Mapping) else {}
        if weapon_id and weapon_id in weapon_map:
            yield str(weapon_map[weapon_id])
    elif category_key == "cards":
        underscored = re.sub(r"\s+", "_", title)
        yield f"cards/{underscored}.webp"
        yield f"cards/{title}.webp"


def _paths_under_game_roots(relative_paths: Iterable[str]) -> Iterable[Path]:
    roots = configured_game_asset_roots()
    for relative in relative_paths:
        decoded = _decode_relative_path(relative)
        for root in roots:
            yield root / decoded


def _game_asset_candidates(category: str, name: str, *, relic_rarity: str = "", module_slot: str = "") -> Iterable[Path]:
    slug = _slug(name)
    title = str(name).strip()
    yield from _paths_under_game_roots(
        _towersmith_mapped_relatives(category, name, relic_rarity=relic_rarity, module_slot=module_slot)
    )
    roots = configured_game_asset_roots()
    if category in {"modules", "module"} and module_slot:
        folder = _module_slot_key(module_slot)
        for root in roots:
            base = root / "modules" / folder
            yield from _candidate_paths(base, title)
            yield from _candidate_paths(base, title.replace(" ", "_"))
            yield from _candidate_paths(base, title.replace("-", " "))
    if category in {"relics", "relic"}:
        rarity_folder = RELIC_RARITY_FOLDERS.get(_slug(relic_rarity), "")
        for root in roots:
            if rarity_folder:
                yield from _candidate_paths(root / "relics" / rarity_folder, slug)
                yield from _candidate_paths(root / "relics" / rarity_folder, title)
            yield from _candidate_paths(root / "relics" / "unmapped", slug)
            yield from _candidate_paths(root / "relics", slug)
    if category in {"ultimate_weapons", "ultimate_weapon", "uw"}:
        weapon_id = UW_NAME_TO_WORKSHOP_ID.get(title, "")
        for root in roots:
            if weapon_id:
                yield from _candidate_paths(root / "ultimate_weapons", f"weapon_{weapon_id}")
            yield from _candidate_paths(root / "ultimate_weapons", slug)
            yield from _candidate_paths(root / "ultimate_weapons", title.replace(" ", "_"))
    if category in {"cards", "card"}:
        for root in roots:
            yield from _candidate_paths(root / "cards", title.replace(" ", "_"))
            yield from _candidate_paths(root / "cards", slug)
    for root in roots:
        yield from _candidate_paths(root / category, slug)
        yield from _candidate_paths(root / category, title)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-") or "unnamed"


def item_icon_key(category: str, name: str) -> str:
    category_slug = _slug(category).replace("-", "_")
    aliases = {
        "ultimate_weapons": "ultimate_weapons",
        "ultimate-weapon": "ultimate_weapons",
        "ultimate_weapon": "ultimate_weapons",
        "uw": "ultimate_weapons",
    }
    category_slug = aliases.get(category_slug, category_slug)
    return normalize_icon_key(f"{category_slug}/{_slug(name)}")


def normalize_icon_key(key: str) -> str:
    raw = str(key or "").replace("\\", "/").strip().strip("/")
    if not raw:
        raise ValueError("Icon key cannot be empty.")
    parts = []
    for part in PurePosixPath(raw).parts:
        if part in {"", ".", ".."}:
            raise ValueError("Icon key contains an unsafe path component.")
        clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", part).strip(".-")
        if not clean:
            raise ValueError("Icon key contains an invalid path component.")
        parts.append(clean.casefold())
    final = "/".join(parts)
    suffix = Path(final).suffix.casefold()
    if suffix in SUPPORTED_EXTENSIONS:
        final = final[: -len(suffix)]
    return final


def _candidate_paths(root: Path, relative_or_key: str) -> Iterable[Path]:
    relative = str(relative_or_key).replace("\\", "/").strip("/")
    path = root / relative
    if path.suffix.casefold() in SUPPORTED_EXTENSIONS:
        yield path
        return
    for suffix in SUPPORTED_EXTENSIONS:
        yield path.with_suffix(suffix)


def custom_icon_path(key: str) -> Optional[Path]:
    safe_key = normalize_icon_key(key)
    for path in _candidate_paths(custom_icon_root(), safe_key):
        if path.is_file():
            return path
    return None


def resolve_icon_path(
    default_relative: str,
    custom_key: Optional[str] = None,
    fallback_relative: Optional[str] = None,
    *,
    game_category: Optional[str] = None,
    game_name: Optional[str] = None,
    relic_rarity: str = "",
    module_slot: str = "",
) -> Optional[Path]:
    key = normalize_icon_key(custom_key or default_relative)
    custom = custom_icon_path(key)
    if custom:
        return custom
    if game_category and game_name:
        external = _first_existing(
            _game_asset_candidates(
                game_category,
                game_name,
                relic_rarity=relic_rarity,
                module_slot=module_slot,
            )
        )
        if external:
            return external
    for path in _candidate_paths(ASSET_ROOT, default_relative):
        if path.is_file():
            return path
    if fallback_relative:
        fallback_key = normalize_icon_key(fallback_relative)
        fallback_custom = custom_icon_path(fallback_key)
        if fallback_custom:
            return fallback_custom
        for path in _candidate_paths(ASSET_ROOT, fallback_relative):
            if path.is_file():
                return path
    return None


def _path_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _icon_source_label(resolved: Optional[Path], custom: Optional[Path]) -> str:
    if not resolved:
        return "missing"
    if custom and resolved == custom:
        return "custom"
    if _path_under_root(resolved, ASSET_ROOT):
        return "default"
    for root in configured_game_asset_roots():
        if _path_under_root(resolved, root):
            return "external"
    return "default"


def icon_source_info(
    default_relative: str,
    custom_key: Optional[str] = None,
    fallback_relative: Optional[str] = None,
    *,
    game_category: Optional[str] = None,
    game_name: Optional[str] = None,
    relic_rarity: str = "",
    module_slot: str = "",
) -> Dict[str, Any]:
    key = normalize_icon_key(custom_key or default_relative)
    custom = custom_icon_path(key)
    resolved = resolve_icon_path(
        default_relative,
        key,
        fallback_relative,
        game_category=game_category,
        game_name=game_name,
        relic_rarity=relic_rarity,
        module_slot=module_slot,
    )
    return {
        "key": key,
        "source": _icon_source_label(resolved, custom),
        "path": str(resolved) if resolved else "",
        "custom_path": str(custom) if custom else "",
        "exists": bool(resolved),
    }


def fixed_icon_status() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for spec in FIXED_ICON_SPECS:
        info = icon_source_info(spec["default"], spec["key"])
        rows.append({**spec, **info})
    return rows


def _validate_raster(payload: bytes, suffix: str) -> Dict[str, Any]:
    if not payload:
        raise ValueError("The selected file is empty.")
    if len(payload) > MAX_ICON_BYTES:
        raise ValueError(f"Icon exceeds the {MAX_ICON_BYTES // (1024 * 1024)} MB limit.")
    if suffix.casefold() not in UPLOAD_EXTENSIONS:
        raise ValueError("Use PNG, WEBP, JPG, or JPEG for uploaded icon overrides.")
    try:
        from PIL import Image
        with Image.open(io.BytesIO(payload)) as image:
            image.verify()
        with Image.open(io.BytesIO(payload)) as image:
            width, height = image.size
            image_format = str(image.format or "").upper()
    except Exception as exc:
        raise ValueError(f"The uploaded file is not a valid raster image: {exc}") from exc
    if width < 8 or height < 8:
        raise ValueError("Icon dimensions must be at least 8×8 pixels.")
    if width > 8192 or height > 8192:
        raise ValueError("Icon dimensions may not exceed 8192×8192 pixels.")
    return {"width": width, "height": height, "format": image_format, "bytes": len(payload)}


def remove_custom_icon(key: str) -> bool:
    safe_key = normalize_icon_key(key)
    removed = False
    for path in _candidate_paths(custom_icon_root(), safe_key):
        if path.exists():
            path.unlink()
            removed = True
    return removed


def save_custom_icon(key: str, filename: str, payload: bytes) -> Dict[str, Any]:
    safe_key = normalize_icon_key(key)
    suffix = Path(filename or "").suffix.casefold()
    if suffix == ".jpeg":
        suffix = ".jpg"
    metadata = _validate_raster(payload, suffix)
    remove_custom_icon(safe_key)
    destination = custom_icon_root() / f"{safe_key}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    return {"key": safe_key, "path": str(destination), **metadata}


def export_custom_icon_pack() -> bytes:
    root = custom_icon_root()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        files = []
        if root.exists():
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.casefold() not in UPLOAD_EXTENSIONS:
                    continue
                relative = path.relative_to(root).as_posix()
                archive.writestr(f"custom_icons/{relative}", path.read_bytes())
                files.append(relative)
        manifest = {
            "format": "tower-optimizer-icon-pack",
            "format_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
        }
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr(
            "README.txt",
            "Tower Optimizer custom icon pack\n"
            "Place files under custom_icons/<category>/<slug>.png.\n"
            "Uploaded artwork must be used and redistributed only with appropriate permission.\n",
        )
    return buffer.getvalue()


def import_custom_icon_pack(payload: bytes) -> Dict[str, Any]:
    if not payload:
        raise ValueError("The selected ZIP file is empty.")
    if len(payload) > MAX_PACK_BYTES:
        raise ValueError(f"Icon pack exceeds the {MAX_PACK_BYTES // (1024 * 1024)} MB limit.")
    installed: List[Dict[str, Any]] = []
    skipped: List[str] = []
    errors: List[str] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            raw_name = info.filename.replace("\\", "/").strip("/")
            parts = list(PurePosixPath(raw_name).parts)
            if parts and parts[0].casefold() == "custom_icons":
                parts = parts[1:]
            if not parts or raw_name.casefold() in {"manifest.json", "readme.txt"}:
                continue
            suffix = Path(parts[-1]).suffix.casefold()
            if suffix not in UPLOAD_EXTENSIONS:
                skipped.append(raw_name)
                continue
            if any(part in {"", ".", ".."} for part in parts):
                errors.append(f"Unsafe path: {raw_name}")
                continue
            if info.file_size > MAX_ICON_BYTES:
                errors.append(f"Too large: {raw_name}")
                continue
            key = "/".join(parts)
            try:
                result = save_custom_icon(key, parts[-1], archive.read(info))
                installed.append(result)
            except Exception as exc:
                errors.append(f"{raw_name}: {exc}")
    return {"installed": installed, "skipped": skipped, "errors": errors}


def custom_icon_count() -> int:
    root = custom_icon_root()
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file() and path.suffix.casefold() in UPLOAD_EXTENSIONS)


def towersmith_icon_paths_loaded() -> bool:
    return bool(_towersmith_icon_paths())


__all__ = [
    "ASSET_ROOT", "CUSTOM_ICON_ROOT", "FIXED_ICON_SPECS", "GAME_DATA_ROOT", "SUPPORTED_EXTENSIONS",
    "UPLOAD_EXTENSIONS", "UW_NAME_TO_WORKSHOP_ID", "configured_game_asset_roots", "custom_icon_count",
    "custom_icon_path", "custom_icon_root", "export_custom_icon_pack", "fixed_icon_status", "icon_source_info",
    "import_custom_icon_pack", "item_icon_key", "normalize_icon_key", "remove_custom_icon", "resolve_icon_path",
    "save_custom_icon", "towersmith_icon_paths_loaded",
]

# Backward-compatible constant for callers that only need the conventional path.
CUSTOM_ICON_ROOT = _custom_icons_dir()
