"""Streamlit page for Battle Performance Learning."""
from __future__ import annotations

from datetime import datetime, time, timezone
import csv
import io
import json
import re
from typing import Any, Callable, Dict, Mapping, MutableMapping

import pandas as pd
import streamlit as st

from .battle_learning import (
    PLAY_STYLES,
    RUN_TYPES,
    add_upgrade_event,
    apply_run_correction,
    battle_rows,
    build_battle_learning_report,
    delete_run,
    delete_upgrade_event,
    ensure_battle_learning_state,
    export_battle_learning_json,
    import_runs,
    prepare_import_batch,
    runs_to_csv,
    upgrade_events,
)


def _split_reports(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks = re.split(r"(?im)(?=^\s*Battle Report\s*$)", text)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    if len(chunks) == 1 and "Battle Report" not in chunks[0]:
        return chunks
    return chunks


def _clean_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _csv_to_runs(payload: bytes, parse_number: Callable[[Any], Any]) -> list[Dict[str, Any]]:
    text = payload.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    runs = []
    aliases = {
        "id": "id", "timestamp": "battle_date", "date": "battle_date", "battle_date": "battle_date",
        "tier": "tier", "wave": "wave", "killed_by": "killed_by", "cause": "killed_by",
        "run_type": "run_type", "play_style": "play_style", "notes": "notes",
        "duration_hours": "duration_hours", "real_time_hours": "duration_hours",
        "coins": "coins_earned", "coins_earned": "coins_earned", "coins_hour": "coins_per_hour",
        "coins_per_hour": "coins_per_hour", "cells": "cells_earned", "cells_earned": "cells_earned",
        "cells_hour": "cells_per_hour", "cells_per_hour": "cells_per_hour",
    }
    for source in reader:
        run: Dict[str, Any] = {"imported_at": datetime.now(timezone.utc).isoformat()}
        for raw_key, raw_value in source.items():
            key = aliases.get(_clean_key(raw_key))
            if not key or raw_value in (None, ""):
                continue
            if key in {"tier", "wave"}:
                parsed = parse_number(raw_value)
                run[key] = int(parsed or 0)
            elif key in {"coins_earned", "coins_per_hour", "cells_earned", "cells_per_hour", "duration_hours"}:
                parsed = parse_number(raw_value)
                run[key] = float(parsed or 0.0)
            else:
                run[key] = raw_value
        duration_hours = float(run.pop("duration_hours", 0.0) or 0.0)
        if duration_hours > 0:
            run["real_seconds"] = int(duration_hours * 3600)
        runs.append(run)
    return runs


def _json_to_runs(payload: bytes) -> list[Dict[str, Any]]:
    data = json.loads(payload.decode("utf-8-sig"))
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, Mapping)]
    if isinstance(data, Mapping):
        if isinstance(data.get("runs"), list):
            return [dict(item) for item in data["runs"] if isinstance(item, Mapping)]
        report = data.get("report")
        if isinstance(report, Mapping) and isinstance(report.get("runs"), list):
            rows = []
            for item in report["runs"]:
                if not isinstance(item, Mapping):
                    continue
                rows.append({
                    "id": item.get("ID"), "battle_date": item.get("Timestamp") or item.get("Date"),
                    "tier": item.get("Tier"), "wave": item.get("Wave"), "killed_by": item.get("Killed By"),
                    "run_type": item.get("Run Type"), "play_style": item.get("Play Style"),
                    "real_seconds": float(item.get("Duration Hours") or 0) * 3600,
                    "coins_earned": item.get("Coins"), "coins_per_hour": item.get("Coins / Hour"),
                    "cells_earned": item.get("Cells"), "cells_per_hour": item.get("Cells / Hour"),
                    "notes": item.get("Notes", ""),
                })
            return rows
        return [dict(data)]
    return []


def _preview_rows(runs: list[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    return [
        {
            "Battle Date": run.get("battle_date"), "Tier": run.get("tier"), "Wave": run.get("wave"),
            "Killed By": run.get("killed_by"), "Coins / Hour": run.get("coins_per_hour"),
            "Cells / Hour": run.get("cells_per_hour"), "Real Seconds": run.get("real_seconds"),
        }
        for run in runs
    ]


def _fmt_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    for suffix, divisor in (("S", 1e24), ("s", 1e21), ("Q", 1e18), ("q", 1e15), ("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(number) >= divisor:
            return f"{number / divisor:.2f}{suffix}"
    return f"{number:,.2f}"


def _recommendation_card(title: str, row: Mapping[str, Any] | None, metric: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        if not row:
            st.caption("Not enough qualifying runs yet.")
            return
        st.metric(f"Tier {int(row.get('Tier', 0))}", _fmt_number(row.get(metric, 0)))
        st.caption(
            f"{int(row.get('Runs', 0))} run(s) · median wave {int(float(row.get('Median Wave', 0))):,} · "
            f"confidence {row.get('Confidence', 'Low')}"
        )


def render_battle_learning_page(
    profile: MutableMapping[str, Any], *,
    save_profile: Callable[[str, Dict[str, Any]], None],
    safe_profile_filename: Callable[[str], str],
    parse_battle_report: Callable[[str], Dict[str, Any]],
    parse_tower_number: Callable[[Any], Any],
    bump_revision: Callable[[], None],
    app_version: str,
) -> None:
    state = ensure_battle_learning_state(profile)
    report = build_battle_learning_report(profile)
    rows = report["runs"]

    st.header("Battle Performance Learning")
    st.caption(
        "Learns from repeated Battle Reports using same-tier medians and visible sample sizes. "
        "Observed changes are correlations, not proof that one upgrade caused a result."
    )

    recommendations = report.get("farming_recommendations", {})
    deaths = report.get("death_summary", [])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saved runs", len(rows))
    c2.metric("Tiers sampled", len(report.get("tier_performance", [])))
    c3.metric("Upgrade comparisons", len(report.get("upgrade_impacts", [])))
    c4.metric("Most common death", deaths[0]["Cause"] if deaths else "No reports")

    tabs = st.tabs([
        "Overview", "Farming Tiers", "Trends", "Upgrade Impact",
        "Import & Review", "Settings & Export",
    ])

    with tabs[0]:
        st.subheader("Current learning summary")
        r1, r2, r3 = st.columns(3)
        with r1:
            _recommendation_card("Best coins/hour tier", recommendations.get("coins"), "Median Coins / Hour")
        with r2:
            _recommendation_card("Best cells/hour tier", recommendations.get("cells"), "Median Cells / Hour")
        with r3:
            _recommendation_card("Best balanced farming tier", recommendations.get("balanced"), "Balanced Score")

        r4, r5 = st.columns(2)
        with r4:
            _recommendation_card("Best active-play tier", recommendations.get("active"), "Median Coins / Hour")
        with r5:
            _recommendation_card("Best overnight tier", recommendations.get("overnight"), "Median Cells / Hour")

        st.subheader("Detected bottlenecks")
        st.dataframe(pd.DataFrame(report.get("bottlenecks", [])), use_container_width=True, hide_index=True)

        modifiers = report.get("feedback_modifiers", {})
        st.subheader("Observed recommendation feedback")
        if modifiers:
            modifier_rows = [
                {
                    "Domain": domain,
                    "Priority Multiplier": details.get("multiplier"),
                    "Observed Change %": details.get("observed_change_percent"),
                    "Comparable Events": details.get("samples"),
                    "Reason": details.get("reason"),
                }
                for domain, details in modifiers.items()
            ]
            st.dataframe(pd.DataFrame(modifier_rows), use_container_width=True, hide_index=True)
            st.caption("Learning adjustments are deliberately capped and only use moderate/high-confidence comparisons.")
        else:
            st.info("No recommendation weights have been adjusted. More dated before/after runs are needed, or observed feedback is disabled.")

    with tabs[1]:
        st.subheader("Tier performance")
        tier_rows = report.get("tier_performance", [])
        if tier_rows:
            st.dataframe(pd.DataFrame(tier_rows), use_container_width=True, hide_index=True)
            tier_frame = pd.DataFrame(tier_rows).set_index("Tier")
            chart_columns = [column for column in ["Median Coins / Hour", "Median Cells / Hour", "Median Wave"] if column in tier_frame]
            selected_metric = st.selectbox("Tier chart metric", chart_columns, key="battle_tier_chart_metric")
            st.bar_chart(tier_frame[[selected_metric]])
        else:
            st.info("Import Battle Reports to compare farming tiers.")

        if deaths:
            st.subheader("Causes of death")
            death_frame = pd.DataFrame(deaths)
            st.dataframe(death_frame, use_container_width=True, hide_index=True)
            st.bar_chart(death_frame.set_index("Cause")[["Runs"]])

    with tabs[2]:
        st.subheader("Performance over time")
        tiers = sorted({int(row["Tier"]) for row in rows if int(row["Tier"]) > 0})
        tier_choice = st.selectbox("Tier filter", ["All tiers", *[f"Tier {tier}" for tier in tiers]], key="battle_trend_tier")
        selected_tier = None if tier_choice == "All tiers" else int(tier_choice.split()[-1])
        trend = [row for row in rows if selected_tier is None or int(row["Tier"]) == selected_tier]
        if trend:
            frame = pd.DataFrame(trend)
            frame["Run Label"] = [
                f"{row.get('Date')} · T{int(row.get('Tier', 0))} · #{index + 1}"
                for index, row in enumerate(trend)
            ]
            metric = st.selectbox(
                "Trend metric", ["Coins / Hour", "Cells / Hour", "Wave", "Duration Hours", "Coins / Wave"],
                key="battle_trend_metric",
            )
            st.line_chart(frame.set_index("Run Label")[[metric]])
            st.dataframe(
                frame[["Date", "Tier", "Wave", "Killed By", "Duration Hours", "Coins / Hour", "Cells / Hour", "Run Type", "Play Style"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No reports match the selected tier.")

    with tabs[3]:
        st.subheader("Before-and-after upgrade comparisons")
        impacts = report.get("upgrade_impacts", [])
        if impacts:
            st.dataframe(pd.DataFrame(impacts), use_container_width=True, hide_index=True)
        else:
            st.info("Mark planner items complete or add a manual upgrade event to begin comparisons.")

        with st.expander("Add a manual upgrade completion", expanded=not impacts):
            e1, e2 = st.columns(2)
            with e1:
                upgrade_name = st.text_input("Upgrade", key="battle_event_upgrade")
                event_system = st.text_input("System", value="Manual", key="battle_event_system")
                event_resource = st.text_input("Resource", value="Unknown", key="battle_event_resource")
            with e2:
                event_date = st.date_input("Completion date", key="battle_event_date")
                event_time = st.time_input("Completion time", value=time(12, 0), key="battle_event_time")
                event_domain = st.selectbox(
                    "Domain", ["Auto", "Economy", "Damage", "Survivability", "Regen / Recovery", "Modules", "Utility"],
                    key="battle_event_domain",
                )
            event_notes = st.text_area("Notes", key="battle_event_notes")
            if st.button("Add upgrade event", type="primary", key="battle_add_event", disabled=not upgrade_name.strip()):
                completed_at = datetime.combine(event_date, event_time, tzinfo=timezone.utc).isoformat()
                add_upgrade_event(
                    profile, upgrade=upgrade_name, completed_at=completed_at,
                    system=event_system, resource=event_resource, domain=event_domain, notes=event_notes,
                )
                save_profile(profile["name"], profile)
                st.success("Upgrade event added.")
                st.rerun()

        manual_events = [event for event in upgrade_events(profile) if event.get("source") == "Manual"]
        if manual_events:
            labels = {f"{event.get('completed_at')} · {event.get('upgrade')}": event for event in manual_events}
            selected = st.selectbox("Manual event to remove", list(labels), key="battle_delete_event_select")
            if st.button("Remove selected manual event", key="battle_delete_event"):
                delete_upgrade_event(profile, str(labels[selected].get("id")))
                save_profile(profile["name"], profile)
                st.rerun()

    with tabs[4]:
        st.subheader("Bulk import")
        st.caption("Paste several reports together or upload TXT, JSON, or CSV. Duplicate fingerprints are skipped by default.")
        bulk_text = st.text_area("Battle Report text", height=240, key="battle_bulk_text")
        uploaded = st.file_uploader(
            "Optional battle-history file", type=["txt", "json", "csv"], key="battle_bulk_file"
        )
        if st.button("Parse import batch", key="battle_parse_batch"):
            parsed: list[Dict[str, Any]] = []
            errors: list[str] = []
            for chunk in _split_reports(bulk_text):
                try:
                    parsed.append(parse_battle_report(chunk))
                except Exception as exc:
                    errors.append(str(exc))
            if uploaded is not None:
                try:
                    suffix = uploaded.name.rsplit(".", 1)[-1].casefold()
                    payload = uploaded.getvalue()
                    if suffix == "txt":
                        for chunk in _split_reports(payload.decode("utf-8-sig", errors="replace")):
                            parsed.append(parse_battle_report(chunk))
                    elif suffix == "json":
                        parsed.extend(_json_to_runs(payload))
                    elif suffix == "csv":
                        parsed.extend(_csv_to_runs(payload, parse_tower_number))
                except Exception as exc:
                    errors.append(f"{uploaded.name}: {exc}")
            prepared = prepare_import_batch(profile.get("runs", []), parsed)
            st.session_state["battle_import_preview"] = prepared
            st.session_state["battle_import_errors"] = errors

        prepared = st.session_state.get("battle_import_preview")
        errors = st.session_state.get("battle_import_errors", [])
        if errors:
            for error in errors:
                st.warning(error)
        if prepared:
            p1, p2, p3 = st.columns(3)
            p1.metric("Unique", len(prepared.get("unique", [])))
            p2.metric("Duplicates", len(prepared.get("duplicates", [])))
            p3.metric("Invalid", len(prepared.get("invalid", [])))
            if prepared.get("unique"):
                st.dataframe(pd.DataFrame(_preview_rows(prepared["unique"])), use_container_width=True, hide_index=True)
            keep_duplicates = st.checkbox("Import detected duplicates too", value=False, key="battle_keep_duplicates")
            if st.button("Import parsed reports", type="primary", key="battle_import_batch", disabled=not prepared.get("unique") and not (keep_duplicates and prepared.get("duplicates"))):
                candidates = [*prepared.get("unique", []), *prepared.get("duplicates", [])]
                result = import_runs(profile, candidates, allow_duplicates=keep_duplicates, batch_label="Battle Learning bulk import")
                save_profile(profile["name"], profile)
                st.session_state.pop("battle_import_preview", None)
                st.session_state.pop("battle_import_errors", None)
                st.success(f"Imported {len(result.get('added', []))} report(s).")
                st.rerun()

        st.divider()
        st.subheader("Review and correct saved reports")
        saved_rows = battle_rows(profile)
        if saved_rows:
            options = {
                f"{row['Date']} · T{row['Tier']} W{row['Wave']} · {row['Killed By']} · {str(row['ID'])[-8:]}": row
                for row in reversed(saved_rows)
            }
            selected_label = st.selectbox("Saved report", list(options), key="battle_review_run")
            selected_row = options[selected_label]
            run_id = str(selected_row["ID"])
            source_run = next(run for run in profile.get("runs", []) if str(run.get("id")) == run_id)
            c1, c2, c3 = st.columns(3)
            with c1:
                edit_date = st.text_input("Battle date/time", value=str(source_run.get("battle_date") or ""), key=f"battle_edit_date_{run_id}")
                edit_tier = st.number_input("Tier", min_value=1, value=max(1, int(source_run.get("tier", 1) or 1)), step=1, key=f"battle_edit_tier_{run_id}")
                edit_wave = st.number_input("Wave", min_value=1, value=max(1, int(source_run.get("wave", 1) or 1)), step=1, key=f"battle_edit_wave_{run_id}")
            with c2:
                edit_cause = st.text_input("Killed by", value=str(source_run.get("killed_by") or "Unknown"), key=f"battle_edit_cause_{run_id}")
                edit_hours = st.number_input("Real duration (hours)", min_value=0.0, value=float(source_run.get("real_seconds", 0) or 0) / 3600.0, step=0.05, key=f"battle_edit_hours_{run_id}")
                edit_run_type = st.selectbox("Run type", RUN_TYPES, index=RUN_TYPES.index(source_run.get("run_type", "Auto")) if source_run.get("run_type", "Auto") in RUN_TYPES else 0, key=f"battle_edit_type_{run_id}")
            with c3:
                edit_coins = st.number_input("Coins earned", min_value=0.0, value=float(source_run.get("coins_earned", 0) or 0), format="%.2f", key=f"battle_edit_coins_{run_id}")
                edit_cells = st.number_input("Cells earned", min_value=0.0, value=float(source_run.get("cells_earned", 0) or 0), format="%.2f", key=f"battle_edit_cells_{run_id}")
                edit_style = st.selectbox("Play style", PLAY_STYLES, index=PLAY_STYLES.index(source_run.get("play_style", "Auto")) if source_run.get("play_style", "Auto") in PLAY_STYLES else 0, key=f"battle_edit_style_{run_id}")
            edit_notes = st.text_area("Notes", value=str(source_run.get("notes") or ""), key=f"battle_edit_notes_{run_id}")
            recalc = st.checkbox("Recalculate hourly rates from earnings and Real Time", value=True, key=f"battle_recalc_{run_id}")
            b1, b2 = st.columns(2)
            if b1.button("Save corrections", type="primary", use_container_width=True, key=f"battle_save_correction_{run_id}"):
                apply_run_correction(profile, run_id, {
                    "battle_date": edit_date, "tier": edit_tier, "wave": edit_wave,
                    "killed_by": edit_cause, "real_seconds": int(edit_hours * 3600),
                    "coins_earned": edit_coins, "cells_earned": edit_cells,
                    "run_type": edit_run_type, "play_style": edit_style, "notes": edit_notes,
                }, recalculate_rates=recalc)
                save_profile(profile["name"], profile)
                bump_revision()
                st.success("Report corrected.")
                st.rerun()
            confirm_delete = b2.checkbox("Confirm delete", key=f"battle_confirm_delete_{run_id}")
            if b2.button("Delete report", use_container_width=True, disabled=not confirm_delete, key=f"battle_delete_run_{run_id}"):
                delete_run(profile, run_id)
                save_profile(profile["name"], profile)
                bump_revision()
                st.rerun()
        else:
            st.info("No saved Battle Reports.")

        quality = report.get("quality", [])
        st.subheader("Parsing and data-quality review")
        if quality:
            st.dataframe(pd.DataFrame(quality), use_container_width=True, hide_index=True)
        else:
            st.success("No battle-history quality findings.")

    with tabs[5]:
        st.subheader("Learning settings")
        settings = state["settings"]
        s1, s2, s3 = st.columns(3)
        with s1:
            settings["minimum_runs_per_tier"] = int(st.number_input(
                "Minimum runs per tier", min_value=1, max_value=20,
                value=int(settings.get("minimum_runs_per_tier", 2)), step=1, key="battle_setting_min_runs",
            ))
            settings["comparison_window_runs"] = int(st.number_input(
                "Before/after runs per side", min_value=1, max_value=20,
                value=int(settings.get("comparison_window_runs", 5)), step=1, key="battle_setting_window",
            ))
        with s2:
            settings["active_max_hours"] = float(st.number_input(
                "Active-play maximum hours", min_value=0.1, max_value=24.0,
                value=float(settings.get("active_max_hours", 2.0)), step=0.25, key="battle_setting_active",
            ))
            settings["overnight_min_hours"] = float(st.number_input(
                "Overnight minimum hours", min_value=0.1, max_value=24.0,
                value=float(settings.get("overnight_min_hours", 4.0)), step=0.25, key="battle_setting_overnight",
            ))
        with s3:
            settings["apply_observed_feedback"] = st.checkbox(
                "Apply observed feedback to priorities", value=bool(settings.get("apply_observed_feedback", True)),
                key="battle_setting_feedback",
            )
            settings["feedback_cap_percent"] = float(st.slider(
                "Maximum learning adjustment", min_value=0.0, max_value=15.0,
                value=float(settings.get("feedback_cap_percent", 8.0)), step=0.5,
                format="%.1f%%", key="battle_setting_cap",
            ))
        if st.button("Save learning settings", type="primary", key="battle_save_settings"):
            save_profile(profile["name"], profile)
            st.success("Battle-learning settings saved.")
            st.rerun()

        st.info(
            "Priority feedback uses only moderate/high-confidence same-tier comparisons and is capped. "
            "Disable it to keep battle history purely informational."
        )
        st.subheader("Export")
        e1, e2 = st.columns(2)
        e1.download_button(
            "Download battle history CSV", data=runs_to_csv(profile),
            file_name=f"{safe_profile_filename(profile['name'])}_battle_history.csv", mime="text/csv",
            use_container_width=True, key="battle_export_csv",
        )
        e2.download_button(
            "Download learning report JSON", data=export_battle_learning_json(profile),
            file_name=f"{safe_profile_filename(profile['name'])}_battle_learning_v{app_version}.json", mime="application/json",
            use_container_width=True, key="battle_export_json",
        )
        st.caption(report.get("method", ""))
