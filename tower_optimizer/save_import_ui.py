"""Streamlit UI for importing playerInfo.dat saves."""
from __future__ import annotations

from typing import Any, Callable, Dict, MutableMapping

import streamlit as st

from .save_parser import apply_player_save_patch, preview_player_save


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
    metrics = st.columns(5)
    labels = [
        ("Workshop", sections.get("workshop", 0)),
        ("Labs", sections.get("labs", 0)),
        ("UWs", sections.get("uw", 0)),
        ("Cards", sections.get("cards", 0)),
        ("Modules", sections.get("modules", 0)),
    ]
    for column, (label, value) in zip(metrics, labels):
        column.metric(label, value)
    st.dataframe(
        [{"Section": name.title(), "Imported values": count} for name, count in sorted(sections.items())],
        use_container_width=True,
        hide_index=True,
    )
    for note in preview.get("notes", []):
        st.caption(f"- {note}")

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
            source_name=str(preview.get("filename") or "playerInfo.dat"),
        )
        save_profile(profile["name"], profile)
        st.session_state.pop(preview_key, None)
        bump_revision()
        st.success(f"Applied save import: {sum(counts.values())} values across {len(counts)} sections.")
        st.rerun()
