"""Streamlit UI for importing playerInfo.dat saves."""
from __future__ import annotations

import html
import re
from typing import Any, Callable, Dict, MutableMapping

import streamlit as st

from .icon_manager import item_icon_key
from .save_parser import apply_player_save_patch, preview_player_save
from .visual_ui import asset_uri


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-") or "unnamed"


def _preview_icon(category: str, name: str, *, slot: str = "", rarity: str = "", fallback: str) -> str:
    return asset_uri(
        f"{category}/{_slug(name)}",
        custom_key=item_icon_key(category, name),
        fallback_relative=fallback,
        game_category=category,
        game_name=name,
        module_slot=slot,
        relic_rarity=rarity,
    )


def _render_preview_gallery(preview: Dict[str, Any]) -> None:
    highlights = preview.get("highlights") or {}
    modules = highlights.get("modules") or []
    relics = highlights.get("relics") or []
    if not modules and not relics:
        return
    st.markdown("#### Resolved preview")
    if modules:
        st.caption("Equipped modules")
        blocks = []
        for row in modules:
            name = str(row.get("name") or "Unknown")
            slot = str(row.get("slot") or "")
            icon = _preview_icon("modules", name, slot=slot, fallback="systems/modules.svg")
            blocks.append(
                f'<div class="module-card"><img src="{icon}" alt="" />'
                f'<h4>{html.escape(name)}</h4>'
                f'<div class="rarity">{html.escape(slot)} · {html.escape(str(row.get("rarity") or ""))}</div>'
                f'<div class="module-stats"><span class="module-chip">Level {html.escape(str(row.get("level") or 0))}</span></div></div>'
            )
        st.markdown(f'<div class="visual-grid">{"".join(blocks)}</div>', unsafe_allow_html=True)
    if relics:
        st.caption("Owned relics (sample)")
        blocks = []
        for row in relics:
            name = str(row.get("name") or "Unknown")
            rarity = str(row.get("rarity") or "")
            icon = _preview_icon("relics", name, rarity=rarity, fallback="placeholders/relic.svg")
            blocks.append(
                f'<div class="relic-card"><img src="{icon}" alt="" />'
                f'<h4>{html.escape(name)}</h4>'
                f'<p>{html.escape(rarity)} · {html.escape(str(row.get("bonus_type") or ""))}</p></div>'
            )
        st.markdown(f'<div class="relic-grid">{"".join(blocks)}</div>', unsafe_allow_html=True)


def render_player_save_import(
    profile: MutableMapping[str, Any],
    *,
    save_profile: Callable[[str, Dict[str, Any]], None],
    bump_revision: Callable[[], None],
    key_prefix: str = "save_import",
) -> None:
    st.subheader("Game save import")
    st.caption(
        "Upload a tower backup `playerInfo.dat` file from the in-game account menu. "
        "Recent battle history from the save (up to 30 runs) is imported into Battle Learning automatically. "
        "The file stays on this computer and is not uploaded anywhere else."
    )
    upload = st.file_uploader(
        "playerInfo.dat",
        type=["dat"],
        key=f"{key_prefix}_upload",
    )
    preview_key = f"{key_prefix}_preview"
    if upload is not None:
        try:
            st.session_state[preview_key] = preview_player_save(upload.getvalue(), upload.name)
        except Exception as exc:
            st.session_state.pop(preview_key, None)
            st.error(f"Could not read save file: {exc}")

    preview = st.session_state.get(preview_key)
    if not preview:
        return

    st.success("Save parsed successfully. Review the section counts before applying.")
    sections = preview.get("sections", {})
    metrics = st.columns(6)
    labels = [
        ("Workshop", sections.get("workshop", 0)),
        ("Labs", sections.get("labs", 0)),
        ("UWs", sections.get("uw", 0)),
        ("Cards", sections.get("cards", 0)),
        ("Relics", sections.get("relics", 0)),
        ("Runs", sections.get("runs", 0)),
    ]
    for column, (label, value) in zip(metrics, labels):
        column.metric(label, value)
    st.dataframe(
        [{"Section": name.title(), "Imported values": count} for name, count in sorted(sections.items())],
        use_container_width=True,
        hide_index=True,
    )
    _render_preview_gallery(preview)
    run_rows = (preview.get("highlights") or {}).get("runs") or []
    if run_rows:
        st.markdown("#### Recent battle history from save")
        st.dataframe(
            [
                {
                    "Date": row.get("battle_date") or "—",
                    "Tier": row.get("tier"),
                    "Wave": row.get("wave"),
                    "Killed By": row.get("killed_by"),
                    "Coins": row.get("coins_earned"),
                }
                for row in run_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
    for note in preview.get("notes", []):
        st.caption(f"- {note}")

    meta = ((preview.get("patch") or {}).get("save_import") or {}).get("metadata") or {}
    with st.expander("Save metadata", expanded=False):
        st.write(
            {
                "Decoded fields": meta.get("field_count"),
                "Data version": preview.get("data_version"),
                "Save revision": preview.get("save_revision"),
                "Battle history rows": meta.get("battle_history_count"),
                "Module registry rows": meta.get("module_records_count"),
            }
        )

    replace = st.checkbox(
        "Replace imported sections instead of merging",
        value=False,
        key=f"{key_prefix}_replace",
    )
    if st.button("Apply game save", type="primary", key=f"{key_prefix}_apply"):
        counts = apply_player_save_patch(
            profile,
            preview["patch"],
            replace=replace,
            import_battle_history=True,
            source_name=str(preview.get("filename") or "playerInfo.dat"),
        )
        save_profile(profile["name"], profile)
        st.session_state.pop(preview_key, None)
        bump_revision()
        st.success(f"Applied save import: {sum(counts.values())} values across {len(counts)} sections.")
        st.rerun()
