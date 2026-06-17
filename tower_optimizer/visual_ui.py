"""Streamlit presentation layer for Tower Optimizer v2 visual preview."""
from __future__ import annotations

import base64
import html
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import pandas as pd
import streamlit as st

from .engines.combined import build_combined_recommendations
from .navigation import NAVIGATION_SECTIONS
from .visual_models import (
    RARITY_ORDER,
    build_card_report,
    build_module_forge_report,
    build_overview_model,
    build_relic_report,
    build_sync_report,
    format_duration,
)
from .icon_manager import (
    FIXED_ICON_SPECS,
    configured_game_asset_roots,
    custom_icon_count,
    custom_icon_path,
    custom_icon_root,
    export_custom_icon_pack,
    fixed_icon_status,
    import_custom_icon_pack,
    item_icon_key,
    remove_custom_icon,
    resolve_icon_path,
    save_custom_icon,
)

ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets"

THEMES: Dict[str, Dict[str, str]] = {
    "Void Cyan": {
        "bg": "#060a11", "bg2": "#0a1320", "panel": "#0d1826", "panel2": "#111f31",
        "text": "#edfaff", "muted": "#8fa9b8", "accent": "#20def7", "accent2": "#9c67ff",
        "gold": "#ffd65a", "danger": "#ff5478", "success": "#4ff0a5", "line": "#20384e",
    },
    "Solar Gold": {
        "bg": "#0d0b07", "bg2": "#171109", "panel": "#1c160d", "panel2": "#251d10",
        "text": "#fff8e7", "muted": "#c8b894", "accent": "#ffb52e", "accent2": "#ff6d5c",
        "gold": "#ffe27a", "danger": "#ff596f", "success": "#70e3a0", "line": "#4a3517",
    },
    "Emerald Grid": {
        "bg": "#050d0a", "bg2": "#071713", "panel": "#0a1d17", "panel2": "#0d281f",
        "text": "#ecfff8", "muted": "#8db7a8", "accent": "#24efad", "accent2": "#1fd6ff",
        "gold": "#ffd769", "danger": "#ff5f7d", "success": "#24efad", "line": "#174739",
    },
}



def render_grouped_navigation(default_page: str = "Overview 2.0") -> str:
    """Render compact expandable navigation and return the selected page.

    Buttons are used instead of one very long radio list so only section names
    remain visible until the user expands a group. The current section opens by
    default and the selected page is retained across Streamlit reruns.
    """
    page_to_section = {page: section for section, pages in NAVIGATION_SECTIONS for page in pages}
    valid_pages = set(page_to_section)
    selected_page = str(st.session_state.get("main_navigation", default_page))
    if selected_page not in valid_pages:
        selected_page = default_page
        st.session_state["main_navigation"] = selected_page

    st.sidebar.markdown("### Navigation")
    st.sidebar.markdown(
        f'<div class="nav-current"><span>Current page</span><strong>{_escape(selected_page)}</strong></div>',
        unsafe_allow_html=True,
    )

    for section, pages in NAVIGATION_SECTIONS:
        with st.sidebar.expander(section, expanded=selected_page in pages):
            for target in pages:
                active = target == selected_page
                label = f"● {target}" if active else target
                if st.button(
                    label,
                    key=f"nav_page_{_slug(section)}_{_slug(target)}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                ):
                    if not active:
                        st.session_state["main_navigation"] = target
                        st.rerun()

    return selected_page


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


@lru_cache(maxsize=256)
def _path_uri(path_text: str, modified_ns: int, size: int) -> str:
    path = Path(path_text)
    suffix = path.suffix.casefold()
    mime = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix, "application/octet-stream")
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def asset_uri(
    relative_path: str,
    custom_key: str | None = None,
    fallback_relative: str | None = None,
    *,
    game_category: str | None = None,
    game_name: str | None = None,
    relic_rarity: str = "",
    module_slot: str = "",
) -> str:
    path = resolve_icon_path(
        relative_path,
        custom_key,
        fallback_relative,
        game_category=game_category,
        game_name=game_name,
        relic_rarity=relic_rarity,
        module_slot=module_slot,
    )
    if not path or not path.exists():
        return ""
    stat = path.stat()
    return _path_uri(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _fmt_number(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return str(value)
    sign = "-" if number < 0 else ""
    number = abs(number)
    for divisor, suffix in [(1e18, "Q"), (1e15, "q"), (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if number >= divisor:
            return f"{sign}{number / divisor:.2f}{suffix}"
    if number.is_integer():
        return f"{sign}{int(number):,}"
    return f"{sign}{number:,.2f}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def render_visual_sidebar(profile: Dict[str, Any], version: str) -> None:
    settings = profile.setdefault("settings", {})
    settings.setdefault("visual_theme", "Void Cyan")
    settings.setdefault("visual_density", "Comfortable")
    settings.setdefault("visual_motion", True)
    logo = asset_uri("brand/tower_optimizer.svg")
    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand">
          <img src="{logo}" alt="Tower Optimizer logo" />
          <div><strong>TOWER</strong><span>OPTIMIZER</span><small>{_escape(version)}</small></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption("v2 visual preview controls")
    options = list(THEMES)
    current_theme = str(settings.get("visual_theme", options[0]))
    if current_theme not in options:
        current_theme = options[0]
    settings["visual_theme"] = st.sidebar.selectbox(
        "Visual theme", options, index=options.index(current_theme), key="v2_visual_theme"
    )
    density_options = ["Comfortable", "Compact"]
    density = str(settings.get("visual_density", "Comfortable"))
    if density not in density_options:
        density = density_options[0]
    settings["visual_density"] = st.sidebar.selectbox(
        "Interface density", density_options, index=density_options.index(density), key="v2_visual_density"
    )
    settings["visual_motion"] = st.sidebar.checkbox(
        "Subtle motion", value=bool(settings.get("visual_motion", True)), key="v2_visual_motion"
    )


def apply_visual_theme(profile: Mapping[str, Any]) -> None:
    settings = profile.get("settings", {}) if isinstance(profile.get("settings", {}), Mapping) else {}
    theme_name = str(settings.get("visual_theme", "Void Cyan"))
    theme = THEMES.get(theme_name, THEMES["Void Cyan"])
    compact = str(settings.get("visual_density", "Comfortable")) == "Compact"
    motion = bool(settings.get("visual_motion", True))
    pad = ".65rem" if compact else "1rem"
    card_min = "132px" if compact else "154px"
    animation = "towerPulse 4s ease-in-out infinite" if motion else "none"
    css = f"""
    <style>
      :root {{
        --tower-bg:{theme['bg']}; --tower-bg2:{theme['bg2']}; --tower-panel:{theme['panel']};
        --tower-panel2:{theme['panel2']}; --tower-text:{theme['text']}; --tower-muted:{theme['muted']};
        --tower-accent:{theme['accent']}; --tower-accent2:{theme['accent2']}; --tower-gold:{theme['gold']};
        --tower-danger:{theme['danger']}; --tower-success:{theme['success']}; --tower-line:{theme['line']};
        --tower-pad:{pad}; --tower-card-min:{card_min};
      }}
      @keyframes towerPulse {{0%,100%{{filter:drop-shadow(0 0 7px color-mix(in srgb,var(--tower-accent) 35%,transparent));}}50%{{filter:drop-shadow(0 0 18px color-mix(in srgb,var(--tower-accent) 70%,transparent));}}}}
      [data-testid="stAppViewContainer"] {{
        background:
          radial-gradient(circle at 84% 7%, color-mix(in srgb,var(--tower-accent2) 15%,transparent), transparent 30%),
          radial-gradient(circle at 12% 18%, color-mix(in srgb,var(--tower-accent) 11%,transparent), transparent 32%),
          linear-gradient(160deg,var(--tower-bg),var(--tower-bg2));
        color:var(--tower-text);
      }}
      [data-testid="stHeader"] {{background:transparent;}}
      [data-testid="stSidebar"] {{background:linear-gradient(180deg,var(--tower-panel),var(--tower-bg));border-right:1px solid var(--tower-line);}}
      [data-testid="stSidebar"] * {{color:var(--tower-text);}}
      .block-container {{padding-top:1.25rem; max-width:1500px;}}
      .sidebar-brand {{display:flex;align-items:center;gap:.7rem;margin:.15rem 0 1rem 0;padding:.55rem;border:1px solid var(--tower-line);border-radius:16px;background:linear-gradient(135deg,var(--tower-panel2),transparent);}}
      .sidebar-brand img {{width:52px;height:52px;animation:{animation};}}
      .sidebar-brand strong,.sidebar-brand span,.sidebar-brand small {{display:block;line-height:1;letter-spacing:.12em;}}
      .sidebar-brand strong {{font-size:1.05rem;color:var(--tower-accent);}}
      .sidebar-brand span {{font-size:.78rem;color:var(--tower-text);margin-top:.2rem;}}
      .sidebar-brand small {{font-size:.58rem;color:var(--tower-muted);margin-top:.4rem;letter-spacing:.04em;}}
      .nav-current {{margin:.15rem 0 .7rem;padding:.6rem .7rem;border:1px solid var(--tower-line);border-radius:12px;background:color-mix(in srgb,var(--tower-panel2) 82%,transparent);}}
      .nav-current span {{display:block;color:var(--tower-muted);font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;}}
      .nav-current strong {{display:block;color:var(--tower-accent);font-size:.82rem;margin-top:.18rem;}}
      [data-testid="stSidebar"] details {{border:1px solid color-mix(in srgb,var(--tower-line) 80%,transparent);border-radius:12px;background:color-mix(in srgb,var(--tower-panel) 88%,transparent);margin-bottom:.42rem;overflow:hidden;}}
      [data-testid="stSidebar"] details[open] {{border-color:color-mix(in srgb,var(--tower-accent) 38%,var(--tower-line));background:linear-gradient(145deg,color-mix(in srgb,var(--tower-accent) 5%,var(--tower-panel2)),var(--tower-panel));}}
      [data-testid="stSidebar"] details summary {{font-weight:800;letter-spacing:.015em;}}
      [data-testid="stSidebar"] details [data-testid="stButton"] button {{justify-content:flex-start;text-align:left;border-radius:9px;min-height:2.15rem;padding:.35rem .55rem;}}
      .tower-hero {{display:flex;align-items:center;gap:1rem;padding:1rem 1.2rem;margin-bottom:1rem;border:1px solid var(--tower-line);border-radius:22px;background:linear-gradient(125deg,color-mix(in srgb,var(--tower-panel2) 92%,transparent),color-mix(in srgb,var(--tower-accent2) 12%,transparent));box-shadow:0 18px 55px rgba(0,0,0,.25);overflow:hidden;position:relative;}}
      .tower-hero:after {{content:"";position:absolute;right:-80px;top:-100px;width:250px;height:250px;border:1px solid color-mix(in srgb,var(--tower-accent) 35%,transparent);border-radius:50%;box-shadow:0 0 0 34px color-mix(in srgb,var(--tower-accent) 4%,transparent),0 0 0 70px color-mix(in srgb,var(--tower-accent2) 3%,transparent);}}
      .tower-hero img {{width:76px;height:76px;z-index:1;animation:{animation};}}
      .tower-hero-copy {{z-index:1;flex:1;}}
      .tower-kicker {{color:var(--tower-accent);font-size:.72rem;font-weight:800;letter-spacing:.22em;text-transform:uppercase;}}
      .tower-hero h1 {{margin:.15rem 0 0;font-size:clamp(1.8rem,3.2vw,3rem);line-height:1;color:var(--tower-text);}}
      .tower-hero p {{margin:.5rem 0 0;color:var(--tower-muted);}}
      .tower-version {{z-index:1;border:1px solid var(--tower-accent);color:var(--tower-accent);padding:.4rem .7rem;border-radius:999px;font-size:.74rem;font-weight:800;white-space:nowrap;}}
      .section-heading {{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;margin:1.5rem 0 .75rem;}}
      .section-heading h2 {{margin:0;color:var(--tower-text);font-size:1.35rem;}}
      .section-heading span {{color:var(--tower-muted);font-size:.83rem;}}
      .visual-grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(var(--tower-card-min),1fr));gap:.75rem;}}
      .metric-card,.system-card,.recommendation-card,.uw-card,.module-card,.relic-card {{border:1px solid var(--tower-line);background:linear-gradient(150deg,var(--tower-panel2),var(--tower-panel));border-radius:18px;padding:var(--tower-pad);box-shadow:0 12px 30px rgba(0,0,0,.18);}}
      .metric-card {{min-height:112px;position:relative;overflow:hidden;}}
      .metric-card img {{width:42px;height:42px;position:absolute;right:.8rem;top:.8rem;opacity:.88;}}
      .metric-card .label {{color:var(--tower-muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.11em;font-weight:700;}}
      .metric-card .value {{color:var(--tower-text);font-size:1.65rem;font-weight:850;margin-top:.45rem;}}
      .metric-card .detail {{color:var(--tower-accent);font-size:.72rem;margin-top:.25rem;}}
      .status-pill {{display:inline-flex;align-items:center;gap:.35rem;border-radius:999px;padding:.26rem .58rem;font-size:.7rem;font-weight:800;border:1px solid var(--tower-line);background:color-mix(in srgb,var(--tower-panel2) 70%,transparent);}}
      .status-pill.good,.status-pill.excellent {{color:var(--tower-success);border-color:color-mix(in srgb,var(--tower-success) 45%,var(--tower-line));}}
      .status-pill.review {{color:var(--tower-gold);border-color:color-mix(in srgb,var(--tower-gold) 45%,var(--tower-line));}}
      .status-pill.warning {{color:var(--tower-danger);border-color:color-mix(in srgb,var(--tower-danger) 45%,var(--tower-line));}}
      .recommendation-card {{display:grid;grid-template-columns:46px 1fr auto;gap:.8rem;align-items:center;margin-bottom:.65rem;}}
      .recommendation-rank {{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(135deg,var(--tower-accent),var(--tower-accent2));color:#041017;font-weight:900;font-size:1.05rem;}}
      .recommendation-card h3 {{margin:0;font-size:1rem;color:var(--tower-text);}}
      .recommendation-card p {{margin:.3rem 0 0;color:var(--tower-muted);font-size:.78rem;}}
      .recommendation-score {{text-align:right;color:var(--tower-accent);font-weight:850;font-size:.9rem;}}
      .uw-card {{text-align:center;position:relative;overflow:hidden;}}
      .uw-card img {{width:74px;height:74px;display:block;margin:0 auto .35rem;}}
      .uw-card h3 {{margin:.1rem 0;color:var(--tower-text);font-size:1rem;}}
      .uw-card .cooldown {{font-size:1.45rem;font-weight:900;color:var(--tower-accent);}}
      .uw-card .duration {{font-size:.75rem;color:var(--tower-muted);}}
      .uw-card.not-owned {{opacity:.48;filter:grayscale(.85);}}
      .sync-strip {{border:1px solid var(--tower-line);border-radius:18px;background:var(--tower-panel);padding:1rem;margin-top:.8rem;}}
      .timeline-lane {{display:grid;grid-template-columns:44px 1fr;align-items:center;gap:.6rem;margin:.7rem 0;}}
      .timeline-label {{font-weight:900;color:var(--tower-accent);}}
      .timeline-track {{height:18px;background:color-mix(in srgb,var(--tower-line) 55%,transparent);border-radius:999px;position:relative;overflow:visible;}}
      .timeline-marker {{position:absolute;top:2px;width:14px;height:14px;border-radius:50%;transform:translateX(-50%);background:var(--tower-accent);box-shadow:0 0 12px color-mix(in srgb,var(--tower-accent) 75%,transparent);}}
      .timeline-marker.start {{transform:none;left:0!important;background:var(--tower-gold);}}
      .slot-grid {{display:grid;grid-template-columns:repeat(auto-fill,minmax(72px,1fr));gap:.55rem;}}
      .slot-tile {{min-height:72px;border:1px dashed var(--tower-line);border-radius:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--tower-muted);background:color-mix(in srgb,var(--tower-panel) 88%,transparent);}}
      .slot-tile.active {{border-style:solid;border-color:color-mix(in srgb,var(--tower-accent) 55%,var(--tower-line));background:linear-gradient(145deg,color-mix(in srgb,var(--tower-accent) 13%,var(--tower-panel)),var(--tower-panel2));color:var(--tower-text);}}
      .slot-tile strong {{font-size:.78rem;}}
      .slot-tile small {{font-size:.62rem;color:var(--tower-muted);}}
      .module-card {{position:relative;min-height:130px;overflow:hidden;}}
      .module-card.locked:after {{content:"LOCKED";position:absolute;right:.65rem;top:.65rem;color:var(--tower-gold);font-size:.6rem;font-weight:900;letter-spacing:.1em;}}
      .module-card>img {{width:50px;height:50px;object-fit:contain;float:right;margin:.1rem 0 .45rem .6rem;filter:drop-shadow(0 0 10px color-mix(in srgb,var(--tower-accent) 25%,transparent));}}
      .module-card h4 {{margin:0 0 .3rem;color:var(--tower-text);font-size:.9rem;}}
      .module-card .rarity {{color:var(--tower-accent2);font-size:.72rem;font-weight:800;}}
      .module-card .module-stats {{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.8rem;}}
      .module-chip {{border:1px solid var(--tower-line);border-radius:999px;padding:.18rem .45rem;font-size:.65rem;color:var(--tower-muted);}}
      .relic-grid {{display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:.7rem;}}
      .relic-card {{text-align:center;min-height:190px;position:relative;}}
      .relic-card.missing {{opacity:.52;filter:saturate(.3);}}
      .relic-card img {{width:74px;height:74px;margin:.1rem auto .5rem;display:block;}}
      .relic-card h4 {{font-size:.83rem;margin:.25rem 0;color:var(--tower-text);}}
      .relic-card p {{font-size:.68rem;color:var(--tower-muted);margin:.25rem 0;}}
      .relic-owned {{position:absolute;right:.55rem;top:.55rem;width:20px;height:20px;border-radius:50%;display:grid;place-items:center;background:var(--tower-success);color:#03100a;font-size:.68rem;font-weight:900;}}
      .relic-card.missing .relic-owned {{background:var(--tower-line);color:var(--tower-muted);}}
      .icon-source-grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.7rem;}}
      .icon-source-card {{border:1px solid var(--tower-line);background:linear-gradient(145deg,var(--tower-panel2),var(--tower-panel));border-radius:16px;padding:.75rem;display:flex;gap:.7rem;align-items:center;min-height:84px;}}
      .icon-source-card img {{width:54px;height:54px;object-fit:contain;flex:0 0 auto;}}
      .icon-source-card strong {{display:block;color:var(--tower-text);font-size:.82rem;}}
      .icon-source-card small {{display:block;color:var(--tower-muted);font-size:.68rem;margin-top:.25rem;word-break:break-word;}}
      .icon-source-card.custom {{border-color:color-mix(in srgb,var(--tower-success) 55%,var(--tower-line));}}
      .progress-shell {{height:9px;border-radius:999px;background:color-mix(in srgb,var(--tower-line) 65%,transparent);overflow:hidden;}}
      .progress-fill {{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--tower-accent),var(--tower-accent2));}}
      .callout {{border-left:4px solid var(--tower-accent);background:color-mix(in srgb,var(--tower-panel2) 80%,transparent);border-radius:0 14px 14px 0;padding:.75rem 1rem;color:var(--tower-muted);margin:.75rem 0;}}
      .callout strong {{color:var(--tower-text);}}
      div[data-testid="stMetric"] {{background:linear-gradient(145deg,var(--tower-panel2),var(--tower-panel));border:1px solid var(--tower-line);border-radius:16px;padding:.65rem .8rem;}}
      div[data-testid="stMetric"] label,div[data-testid="stMetric"] [data-testid="stMetricDelta"] {{color:var(--tower-muted)!important;}}
      div[data-testid="stMetric"] [data-testid="stMetricValue"] {{color:var(--tower-text)!important;}}
      div[data-baseweb="select"] > div, input, textarea {{background-color:var(--tower-panel)!important;border-color:var(--tower-line)!important;color:var(--tower-text)!important;}}
      .stButton>button {{border-radius:12px;border:1px solid var(--tower-line);background:linear-gradient(145deg,var(--tower-panel2),var(--tower-panel));color:var(--tower-text);}}
      .stButton>button:hover {{border-color:var(--tower-accent);color:var(--tower-accent);}}
      @media(max-width:720px) {{.tower-hero{{align-items:flex-start;}}.tower-version{{display:none;}}.recommendation-card{{grid-template-columns:40px 1fr;}}.recommendation-score{{grid-column:2;text-align:left;}}}}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_app_header(profile: Mapping[str, Any], version: str) -> None:
    logo = asset_uri("brand/tower_optimizer.svg")
    name = _escape(profile.get("name", "default"))
    st.markdown(
        f"""
        <div class="tower-hero">
          <img src="{logo}" alt="Tower Optimizer" />
          <div class="tower-hero-copy">
            <div class="tower-kicker">Player intelligence console</div>
            <h1>The Tower Optimizer</h1>
            <p>Profile <strong>{name}</strong> · recommendations, planning, sync analysis, and progression tracking</p>
          </div>
          <div class="tower-version">v{_escape(version)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="section-heading"><h2>{_escape(title)}</h2><span>{_escape(subtitle)}</span></div>',
        unsafe_allow_html=True,
    )


def _metric_cards(items: Iterable[Mapping[str, Any]]) -> None:
    blocks = []
    for item in items:
        icon = asset_uri(str(item.get("icon", ""))) if item.get("icon") else ""
        img = f'<img src="{icon}" alt="" />' if icon else ""
        blocks.append(
            f"""<div class="metric-card">{img}<div class="label">{_escape(item.get('label'))}</div>
            <div class="value">{_escape(item.get('value'))}</div><div class="detail">{_escape(item.get('detail'))}</div></div>"""
        )
    st.markdown(f'<div class="visual-grid">{"".join(blocks)}</div>', unsafe_allow_html=True)


def _recommendation_cards(rows: Iterable[Mapping[str, Any]], limit: int = 5) -> None:
    blocks = []
    for index, row in enumerate(list(rows)[:limit], start=1):
        why = str(row.get("Why") or "No explanation available")
        if len(why) > 170:
            why = why[:167].rstrip() + "..."
        score = row.get("Priority Index", "—")
        try:
            score_text = f"{float(score):.1f}"
        except (TypeError, ValueError):
            score_text = str(score)
        blocks.append(
            f"""
            <div class="recommendation-card">
              <div class="recommendation-rank">{index}</div>
              <div><h3>{_escape(row.get('Upgrade', 'Recommendation'))}</h3>
              <p>{_escape(row.get('System', ''))} · {_escape(row.get('Resource', ''))} · {_escape(row.get('Cost / Time', ''))}<br>{_escape(why)}</p></div>
              <div class="recommendation-score">{_escape(score_text)}<br><span class="status-pill">{_escape(row.get('Confidence', ''))}</span></div>
            </div>
            """
        )
    if blocks:
        st.markdown("".join(blocks), unsafe_allow_html=True)
    else:
        st.info("No recommendations are available yet. Import or enter more profile data.")


def _uw_cards(report: Mapping[str, Any]) -> None:
    paths = {
        "Golden Tower": "ultimate_weapons/golden_tower.svg",
        "Black Hole": "ultimate_weapons/black_hole.svg",
        "Death Wave": "ultimate_weapons/death_wave.svg",
    }
    blocks = []
    for name, row in report.get("weapons", {}).items():
        owned = bool(row.get("owned"))
        css_class = "uw-card" if owned else "uw-card not-owned"
        cooldown = format_duration(row.get("cooldown_seconds")) if row.get("cooldown_seconds") else "Not set"
        duration = f"Duration {row.get('duration'):g}s" if row.get("duration") else "No duration value"
        blocks.append(
            f"""<div class="{css_class}"><img src="{asset_uri(paths.get(name,''))}" alt="{_escape(name)}" />
            <h3>{_escape(name)}</h3><div class="cooldown">{_escape(cooldown)}</div><div class="duration">{_escape(duration)}</div></div>"""
        )
    st.markdown(f'<div class="visual-grid">{"".join(blocks)}</div>', unsafe_allow_html=True)


def _sync_timeline(report: Mapping[str, Any]) -> None:
    timeline = report.get("timeline", {}) if isinstance(report.get("timeline", {}), Mapping) else {}
    horizon = int(timeline.get("horizon_seconds", 0) or 0)
    if horizon <= 0:
        st.info("Enter owned status and valid cooldowns to draw the timeline.")
        return
    lanes = []
    for lane in timeline.get("lanes", []):
        markers = []
        for marker in lane.get("markers", []):
            percent = min(100.0, max(0.0, 100.0 * float(marker) / horizon))
            cls = "timeline-marker start" if marker == 0 else "timeline-marker"
            markers.append(f'<span class="{cls}" style="left:{percent:.3f}%" title="{format_duration(marker)}"></span>')
        lanes.append(
            f'<div class="timeline-lane"><div class="timeline-label">{_escape(lane.get("short"))}</div><div class="timeline-track">{"".join(markers)}</div></div>'
        )
    st.markdown(
        f'<div class="sync-strip"><strong>Activation timeline · {_escape(format_duration(horizon))}</strong>{"".join(lanes)}</div>',
        unsafe_allow_html=True,
    )


def render_overview_page(profile: Dict[str, Any]) -> None:
    recommendations = build_combined_recommendations(profile, steps=8, candidates_per_path=3, focus="Balanced")
    model = build_overview_model(profile, recommendations)
    _section("Command Center", "A visual test of the future v2 home screen")
    resources = model["resources"]
    _metric_cards([
        {"label": "Coins", "value": _fmt_number(resources.get("coins")), "detail": "Available balance", "icon": "resources/coins.svg"},
        {"label": "Stones", "value": _fmt_number(resources.get("stones")), "detail": "Ultimate Weapon currency", "icon": "resources/stones.svg"},
        {"label": "Gems", "value": _fmt_number(resources.get("gems")), "detail": "Cards, slots, and modules", "icon": "resources/gems.svg"},
        {"label": "Card slots", "value": model["cards"].get("slots", 0), "detail": f"Target {model['cards'].get('target', 0)}", "icon": "systems/cards.svg"},
        {"label": "Relics", "value": f"{model['relics'].get('owned',0)}/{model['relics'].get('total',0)}", "detail": "Owned collection", "icon": "systems/relics.svg"},
        {"label": "Battle reports", "value": model.get("run_count", 0), "detail": f"Latest death: {model.get('latest_death')}", "icon": "systems/modules.svg"},
    ])

    _section("Priority Feed", f"Modeled bottleneck: {model.get('weakest')}")
    _recommendation_cards(model.get("top_recommendations", []), limit=5)

    _section("Ultimate Weapon Sync", model["sync"].get("status", ""))
    _uw_cards(model["sync"])
    status = model["sync"]
    st.markdown(
        f'<div class="callout"><span class="status-pill {_escape(status.get("severity"))}">{_escape(status.get("status"))}</span> '
        f'<strong>Full overlap:</strong> {_escape(status.get("triple_overlap_text"))}<br>{_escape(status.get("recommendation"))}</div>',
        unsafe_allow_html=True,
    )
    _sync_timeline(status)

    _section("Account Pulse", "Recent battle history")
    runs = [row for row in profile.get("runs", []) if isinstance(row, Mapping)]
    if len(runs) >= 2:
        frame = pd.DataFrame([
            {
                "Run": index + 1,
                "Wave": float(row.get("wave", 0) or 0),
                "Coins / Hour": float(row.get("coins_per_hour", 0) or 0),
                "Cells / Hour": float(row.get("cells_per_hour", 0) or 0),
            }
            for index, row in enumerate(runs[-20:])
        ]).set_index("Run")
        st.line_chart(frame[["Wave"]], use_container_width=True)
        st.caption("Additional visual chart treatments will replace the standard chart after the shell is approved.")
    else:
        st.info("Import at least two battle reports to display account performance trends.")


def render_sync_center_page(profile: Dict[str, Any]) -> None:
    _section("GT / BH / DW Sync Center", "Three-way cooldown and activation visualization")
    st.caption("Edit these values here or on the Ultimate Weapons page. Changes update the active profile immediately.")
    columns = st.columns(3)
    names = ["Golden Tower", "Black Hole", "Death Wave"]
    for column, name in zip(columns, names):
        with column:
            uw = profile.setdefault("uw", {}).setdefault(name, {"owned": False, "attributes": {}})
            attrs = uw.setdefault("attributes", {})
            uw["owned"] = st.checkbox("Owned", value=bool(uw.get("owned", False)), key=f"v2_sync_owned_{_slug(name)}")
            attrs["Cooldown"] = int(st.number_input(
                f"{name} cooldown (seconds)", min_value=1, max_value=10000,
                value=max(1, int(float(attrs.get("Cooldown", uw.get("cooldown", 1)) or 1))), step=1,
                key=f"v2_sync_cd_{_slug(name)}", disabled=not uw["owned"],
            ))
            if name != "Death Wave" or "Duration" in attrs:
                attrs["Duration"] = float(st.number_input(
                    f"{name} duration (seconds)", min_value=0.0, max_value=1000.0,
                    value=max(0.0, float(attrs.get("Duration", uw.get("duration", 0)) or 0)), step=1.0,
                    key=f"v2_sync_duration_{_slug(name)}", disabled=not uw["owned"],
                ))
    report = build_sync_report(profile)
    _uw_cards(report)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sync status", report.get("status", "Unknown"))
    c2.metric("Three-way overlap", report.get("triple_overlap_text", "Unavailable"))
    c3.metric("Cooldown spread", format_duration(report.get("cooldown_spread", 0)))
    c4.metric("MVN detected", "Yes" if report.get("mvn_detected") else "No")
    st.markdown(
        f'<div class="callout"><span class="status-pill {_escape(report.get("severity"))}">{_escape(report.get("status"))}</span><br>{_escape(report.get("recommendation"))}</div>',
        unsafe_allow_html=True,
    )
    pair_rows = [
        {
            "Pair": f"{row.get('left_short')} / {row.get('right_short')}",
            "Exact": "Yes" if row.get("exact") else "No",
            "Activation ratio": row.get("ratio"),
            "Overlap interval": row.get("overlap_text"),
        }
        for row in report.get("pairs", [])
    ]
    st.dataframe(pair_rows, use_container_width=True, hide_index=True)
    _sync_timeline(report)
    if report.get("mvn_detected"):
        st.warning("Multiverse Nexus was found in a module slot or preset. This preview deliberately shows raw entered cooldowns; its module-specific cooldown transformation is not applied yet.")


def _slot_grid(slots: int, target: int, selected_cards: Iterable[str] = ()) -> None:
    selected = list(selected_cards)
    total = max(slots, target, 1)
    total = min(total, 40)
    blocks = []
    for index in range(total):
        active = index < slots
        name = selected[index] if index < len(selected) else ("Unlocked" if active else "Planned")
        cls = "slot-tile active" if active else "slot-tile"
        blocks.append(f'<div class="{cls}"><strong>Slot {index + 1}</strong><small>{_escape(name)}</small></div>')
    st.markdown(f'<div class="slot-grid">{"".join(blocks)}</div>', unsafe_allow_html=True)


def render_card_deck_page(profile: Dict[str, Any]) -> None:
    _section("Card Deck", "Slot tracking, collection progress, and preset layout preview")
    cards = profile.setdefault("cards", {"slots": 0, "items": {}})
    cards.setdefault("items", {})
    cards.setdefault("presets", {})
    current_slots = max(0, int(cards.get("slots", 0) or 0))
    cards["slots"] = int(st.number_input("Total card slots unlocked", min_value=0, max_value=50, value=current_slots, step=1, key="v2_card_slots"))
    default_target = max(cards["slots"], int(cards.get("slot_target", cards["slots"] + 1) or cards["slots"] + 1))
    cards["slot_target"] = int(st.number_input("Personal slot target", min_value=max(1, cards["slots"]), max_value=50, value=max(1, default_target), step=1, key="v2_card_target"))
    report = build_card_report(profile)
    _metric_cards([
        {"label": "Unlocked slots", "value": report["slots"], "detail": f"{report['remaining_to_target']} to personal target", "icon": "systems/cards.svg"},
        {"label": "Cards tracked", "value": report["card_count"], "detail": f"{report['owned_cards']} have levels", "icon": "systems/cards.svg"},
        {"label": "Average level", "value": f"{report['average_level']:.2f}", "detail": f"Highest seen {report['max_card_level_seen']}", "icon": "systems/cards.svg"},
        {"label": "Vault slot bonus", "value": report["vault_slots_reported"], "detail": "Reported by imported Vault data", "icon": "systems/cards.svg"},
    ])
    pct = 100.0 * report["progress"]
    st.markdown(f'<div class="progress-shell"><div class="progress-fill" style="width:{pct:.2f}%"></div></div>', unsafe_allow_html=True)
    st.caption(f"Slot progress toward your configured target: {report['slots']} / {report['target']}. The preview does not hardcode a universal maximum.")

    preset_options = ["Farming", "Pushing", "Tournament", "Overnight"]
    preset_name = st.selectbox("Preset preview", preset_options, key="v2_card_preset_name")
    available_cards = sorted(cards["items"])
    stored = [name for name in cards["presets"].get(preset_name, []) if name in available_cards]
    selected = st.multiselect(
        "Cards in this preset", available_cards, default=stored,
        max_selections=max(1, cards["slots"]) if cards["slots"] else None,
        key=f"v2_card_preset_{_slug(preset_name)}",
    )
    cards["presets"][preset_name] = selected
    _slot_grid(report["slots"], report["target"], selected)

    _section("Collection", "Levels and mastery imported from the Cards workbook")
    search = st.text_input("Search cards", key="v2_card_search").casefold().strip()
    rows = []
    for name, value in cards["items"].items():
        if search and search not in name.casefold():
            continue
        if not isinstance(value, Mapping):
            continue
        rows.append({"Card": name, "Level": int(value.get("level", 0) or 0), "Mastery": int(value.get("mastery", 0) or 0)})
    st.dataframe(rows, use_container_width=True, hide_index=True, height=min(650, 38 + max(1, len(rows)) * 35))


def _module_card_html(row: Mapping[str, Any]) -> str:
    locked = " locked" if row.get("locked") else ""
    name = str(row.get("name", "Unknown"))
    icon = asset_uri(
        f"modules/{_slug(name)}",
        custom_key=item_icon_key("modules", name),
        fallback_relative="systems/modules.svg",
        game_category="modules",
        game_name=name,
        module_slot=str(row.get("slot", "")),
    )
    return (
        f'<div class="module-card{locked}"><img src="{icon}" alt="" /><h4>{_escape(name)}</h4>'
        f'<div class="rarity">{_escape(row.get("slot",""))} · {_escape(row.get("rarity",""))}</div>'
        f'<div class="module-stats"><span class="module-chip">Level {_escape(row.get("level",0))}</span>'
        f'<span class="module-chip">Copies {_escape(row.get("copies",0))}</span>'
        f'<span class="module-chip">Sub-effects {len(row.get("substats",[]) or [])}</span></div></div>'
    )


def render_module_forge_page(profile: Dict[str, Any]) -> None:
    _section("Module Forge", "Conservative copy tracking and merge-readiness graphics")
    inventory = profile.setdefault("module_inventory", {})
    forge = profile.setdefault("module_forge", {})
    forge.setdefault("fodder", {})
    for key, record in inventory.items():
        if isinstance(record, dict):
            record.setdefault("copies", 1)
            record.setdefault("locked", False)
    report = build_module_forge_report(profile)
    _metric_cards([
        {"label": "Named modules", "value": report["module_names"], "detail": f"{report['total_copies']} copies entered", "icon": "systems/modules.svg"},
        {"label": "Exact-copy pairs", "value": len(report["exact_copy_candidates"]), "detail": "Candidates requiring review", "icon": "systems/modules.svg"},
        {"label": "Protected", "value": len(report["locked"]), "detail": "Local do-not-consume flags", "icon": "systems/modules.svg"},
        {"label": "Generic fodder", "value": report["fodder_total"], "detail": "Manually entered pool", "icon": "systems/modules.svg"},
    ])
    tabs = st.tabs(["Inventory", "Fodder Pool", "Readiness"])
    with tabs[0]:
        slots = [slot for slot in ["Cannon", "Armor", "Generator", "Core"] if report["by_slot"].get(slot)]
        selected_slot = st.selectbox("Module slot", slots or ["No inventory"], key="v2_module_slot", disabled=not slots)
        slot_rows = report["by_slot"].get(selected_slot, []) if slots else []
        if slot_rows:
            st.markdown(f'<div class="visual-grid">{"".join(_module_card_html(row) for row in slot_rows)}</div>', unsafe_allow_html=True)
            names = [str(row.get("name")) for row in slot_rows]
            selected_name = st.selectbox("Edit module", names, key="v2_module_edit_name")
            selected_row = next(row for row in slot_rows if str(row.get("name")) == selected_name)
            source = inventory[selected_row["key"]]
            c1, c2, c3 = st.columns(3)
            source["copies"] = int(c1.number_input("Copies owned", min_value=0, max_value=999, value=int(source.get("copies", 1) or 0), step=1, key=f"v2_module_copies_{_slug(selected_row['key'])}"))
            source["locked"] = bool(c2.checkbox("Protect from fodder", value=bool(source.get("locked", False)), key=f"v2_module_lock_{_slug(selected_row['key'])}"))
            c3.metric("Imported rarity", source.get("rarity", "Unknown"))
        else:
            st.info("Import the Modules companion workbook to populate the inventory.")
    with tabs[1]:
        st.caption("Enter only generic fodder that you are willing to consume. Named unique modules are never counted here automatically.")
        rarity_options = ["Rare+", "Epic+", "Legendary+"]
        for slot in ["Cannon", "Armor", "Generator", "Core"]:
            st.markdown(f"**{slot}**")
            cols = st.columns(len(rarity_options))
            slot_fodder = forge["fodder"].setdefault(slot, {})
            for col, rarity in zip(cols, rarity_options):
                slot_fodder[rarity] = int(col.number_input(
                    rarity, min_value=0, max_value=999, value=int(slot_fodder.get(rarity, 0) or 0), step=1,
                    key=f"v2_fodder_{_slug(slot)}_{_slug(rarity)}",
                ))
    with tabs[2]:
        refreshed = build_module_forge_report(profile)
        st.markdown(f'<div class="callout"><strong>Safety model:</strong> {_escape(refreshed.get("method"))}</div>', unsafe_allow_html=True)
        candidates = refreshed.get("exact_copy_candidates", [])
        if candidates:
            st.markdown(f'<div class="visual-grid">{"".join(_module_card_html(row) for row in candidates)}</div>', unsafe_allow_html=True)
        else:
            st.info("No named module currently has two or more copies entered.")
        for warning in refreshed.get("warnings", []):
            st.warning(warning)
        st.caption("The exact in-game merge recipe engine will be added only after its rules are represented as versioned game data and regression-tested. This preview focuses on inventory safety and interface behavior.")


def _relic_asset(name: str, rarity: str = "") -> str:
    return asset_uri(
        f"relics/{_slug(name)}",
        custom_key=item_icon_key("relics", name),
        fallback_relative="placeholders/relic.svg",
        game_category="relics",
        game_name=name,
        relic_rarity=rarity,
    )


def render_relic_gallery_page(profile: Dict[str, Any]) -> None:
    _section("Relic Gallery", "Artwork-ready collection grid with automatic placeholders")
    report = build_relic_report(profile)
    _metric_cards([
        {"label": "Owned", "value": report["owned"], "detail": "Relics collected", "icon": "systems/relics.svg"},
        {"label": "Missing", "value": report["missing"], "detail": "Acquisition targets", "icon": "systems/relics.svg"},
        {"label": "Total tracked", "value": report["total"], "detail": "Imported catalog", "icon": "systems/relics.svg"},
        {"label": "Collection", "value": f"{report['progress'] * 100:.1f}%", "detail": "Artwork tiles ready", "icon": "systems/relics.svg"},
    ])
    st.markdown(f'<div class="progress-shell"><div class="progress-fill" style="width:{report["progress"]*100:.2f}%"></div></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 1])
    query = c1.text_input("Search relics", key="v2_relic_search").casefold().strip()
    ownership = c2.selectbox("Ownership", ["All", "Owned", "Missing"], key="v2_relic_ownership")
    rarities = sorted({str(row.get("rarity")) for row in report["rows"]})
    rarity = c3.selectbox("Rarity", ["All", *rarities], key="v2_relic_rarity")
    filtered = []
    for row in report["rows"]:
        if query and query not in str(row.get("name", "")).casefold() and query not in str(row.get("bonus_type", "")).casefold():
            continue
        if ownership == "Owned" and not row.get("owned"):
            continue
        if ownership == "Missing" and row.get("owned"):
            continue
        if rarity != "All" and row.get("rarity") != rarity:
            continue
        filtered.append(row)
    limit = st.slider("Tiles to render", min_value=12, max_value=120, value=min(36, max(12, len(filtered) or 12)), step=12, key="v2_relic_limit")
    blocks = []
    for row in filtered[:limit]:
        cls = "relic-card" if row.get("owned") else "relic-card missing"
        marker = "✓" if row.get("owned") else "·"
        value = row.get("value")
        try:
            bonus = f"{float(value) * 100:g}% {row.get('bonus_type')}" if abs(float(value)) <= 2 else f"{value} {row.get('bonus_type')}"
        except (TypeError, ValueError):
            bonus = str(row.get("bonus_type") or "Bonus unavailable")
        blocks.append(
            f'<div class="{cls}"><div class="relic-owned">{marker}</div><img src="{_relic_asset(str(row.get("name")), str(row.get("rarity") or ""))}" alt="" />'
            f'<h4>{_escape(row.get("name"))}</h4><p>{_escape(row.get("rarity"))}</p><p>{_escape(bonus)}</p></div>'
        )
    if blocks:
        st.markdown(f'<div class="relic-grid">{"".join(blocks)}</div>', unsafe_allow_html=True)
    else:
        st.info("No relics match the current filters.")
    st.caption("Place future artwork in assets/relics using a lowercase hyphenated filename. The gallery automatically falls back to the original placeholder graphic.")


def _icon_status_cards(rows: Iterable[Mapping[str, Any]]) -> None:
    blocks = []
    for row in rows:
        uri = asset_uri(str(row.get("default", "")), custom_key=str(row.get("key", "")))
        source = str(row.get("source", "missing"))
        css = "icon-source-card custom" if source == "custom" else "icon-source-card"
        source_label = "Custom override" if source == "custom" else ("Bundled fallback" if source == "default" else "Missing")
        blocks.append(
            f'<div class="{css}"><img src="{uri}" alt="" /><div><strong>{_escape(row.get("label"))}</strong>'
            f'<small>{_escape(source_label)}<br>{_escape(row.get("key"))}</small></div></div>'
        )
    st.markdown(f'<div class="icon-source-grid">{"".join(blocks)}</div>', unsafe_allow_html=True)


def _profile_artwork_names(profile: Mapping[str, Any], category: str) -> list[str]:
    if category == "Relics":
        relics = profile.get("relics", {}) if isinstance(profile.get("relics", {}), Mapping) else {}
        items = relics.get("items", {}) if isinstance(relics.get("items", {}), Mapping) else {}
        return sorted(str(name) for name in items)
    if category == "Modules":
        inventory = profile.get("module_inventory", {}) if isinstance(profile.get("module_inventory", {}), Mapping) else {}
        names = {
            str(row.get("name", key))
            for key, row in inventory.items()
            if isinstance(row, Mapping) and str(row.get("name", key)).strip()
        }
        return sorted(names)
    if category == "Cards":
        cards = profile.get("cards", {}) if isinstance(profile.get("cards", {}), Mapping) else {}
        items = cards.get("items", {}) if isinstance(cards.get("items", {}), Mapping) else {}
        return sorted(str(name) for name in items)
    return []


def _dynamic_icon_fallback(category: str) -> str:
    return {
        "Relics": "placeholders/relic.svg",
        "Modules": "systems/modules.svg",
        "Cards": "systems/cards.svg",
    }.get(category, "brand/tower_optimizer.svg")


def render_icon_studio_page(profile: Dict[str, Any]) -> None:
    _section("Icon Studio", "Persistent custom artwork overrides without modifying bundled assets")
    st.markdown(
        '<div class="callout"><strong>How it works:</strong> uploaded images are saved under '
        '<code>data/custom_icons</code>. The app checks that folder first, then optional '
        '<code>TOWER_GAME_ASSETS_DIR</code> or <code>TOWER_SMITH_PUBLIC_DIR</code> on your machine, '
        'then bundled original graphics. TowerSmith artwork is used locally with the author\'s permission — see NOTICE.md.</div>',
        unsafe_allow_html=True,
    )
    asset_roots = configured_game_asset_roots()
    if asset_roots:
        st.caption("Local artwork folders: " + ", ".join(str(path) for path in asset_roots))
    else:
        st.caption("Optional: set TOWER_SMITH_PUBLIC_DIR to a local TowerSmith public/ clone for module and relic icons.")
    status_rows = fixed_icon_status()
    fixed_custom = sum(1 for row in status_rows if row.get("source") == "custom")
    fixed_default = sum(1 for row in status_rows if row.get("source") == "default")
    _metric_cards([
        {"label": "Custom files", "value": custom_icon_count(), "detail": "Persistent local artwork", "icon": "brand/tower_optimizer.svg"},
        {"label": "Interface overrides", "value": fixed_custom, "detail": f"of {len(status_rows)} fixed slots", "icon": "systems/modules.svg"},
        {"label": "Bundled fallbacks", "value": fixed_default, "detail": "Used when no override exists", "icon": "systems/relics.svg"},
        {"label": "Storage", "value": "Local", "detail": str(custom_icon_root()), "icon": "resources/gems.svg"},
    ])

    tabs = st.tabs(["Interface Icons", "Collection Artwork", "Icon Packs", "Filename Guide"])
    with tabs[0]:
        _icon_status_cards(status_rows)
        labels = [f"{row['category']} · {row['label']}" for row in status_rows]
        selected_label = st.selectbox("Icon slot", labels, key="v2_icon_fixed_slot")
        selected = status_rows[labels.index(selected_label)]
        c1, c2 = st.columns([1, 2])
        with c1:
            uri = asset_uri(selected["default"], custom_key=selected["key"])
            st.markdown(
                f'<div class="relic-card"><img src="{uri}" alt="" /><h4>{_escape(selected["label"])}</h4>'
                f'<p>{_escape(selected["source"].title())}</p></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.code(f"data/custom_icons/{selected['key']}.png", language=None)
            upload = st.file_uploader(
                "Upload PNG, WEBP, JPG, or JPEG",
                type=["png", "webp", "jpg", "jpeg"],
                key=f"v2_icon_upload_{_slug(selected['key'])}",
                help="Transparent square PNG files around 256×256 or 512×512 usually look best.",
            )
            b1, b2 = st.columns(2)
            if b1.button("Install override", use_container_width=True, disabled=upload is None, key=f"v2_icon_save_{_slug(selected['key'])}"):
                try:
                    result = save_custom_icon(selected["key"], upload.name, upload.getvalue())
                    st.success(f"Installed {result['width']}×{result['height']} override for {selected['label']}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            has_custom = bool(custom_icon_path(selected["key"]))
            if b2.button("Restore bundled icon", use_container_width=True, disabled=not has_custom, key=f"v2_icon_remove_{_slug(selected['key'])}"):
                remove_custom_icon(selected["key"])
                st.success("Custom override removed.")
                st.rerun()

    with tabs[1]:
        st.caption("Collection artwork uses the same lowercase, hyphenated names as the profile. Relic and module pages update automatically.")
        category = st.selectbox("Artwork category", ["Relics", "Modules", "Cards"], key="v2_icon_dynamic_category")
        names = _profile_artwork_names(profile, category)
        use_profile = st.checkbox("Choose an item from this profile", value=bool(names), disabled=not names, key="v2_icon_choose_profile")
        if use_profile and names:
            item_name = st.selectbox("Profile item", names, key=f"v2_icon_item_{_slug(category)}")
        else:
            item_name = st.text_input("Item name", placeholder="Example: Black Hole Digestor", key=f"v2_icon_manual_{_slug(category)}")
        storage_category = category.casefold()
        icon_key = item_icon_key(storage_category, item_name) if item_name.strip() else ""
        fallback = _dynamic_icon_fallback(category)
        if icon_key:
            current_uri = asset_uri(icon_key, custom_key=icon_key, fallback_relative=fallback)
            d1, d2 = st.columns([1, 2])
            with d1:
                st.markdown(
                    f'<div class="relic-card"><img src="{current_uri}" alt="" /><h4>{_escape(item_name)}</h4>'
                    f'<p>{"Custom" if custom_icon_path(icon_key) else "Fallback"}</p></div>',
                    unsafe_allow_html=True,
                )
            with d2:
                st.code(f"data/custom_icons/{icon_key}.png", language=None)
                dynamic_upload = st.file_uploader(
                    f"Upload artwork for {item_name}", type=["png", "webp", "jpg", "jpeg"],
                    key=f"v2_dynamic_upload_{_slug(icon_key)}",
                )
                dsave, dremove = st.columns(2)
                if dsave.button("Install artwork", use_container_width=True, disabled=dynamic_upload is None, key=f"v2_dynamic_save_{_slug(icon_key)}"):
                    try:
                        result = save_custom_icon(icon_key, dynamic_upload.name, dynamic_upload.getvalue())
                        st.success(f"Installed {result['width']}×{result['height']} artwork for {item_name}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                if dremove.button("Remove artwork", use_container_width=True, disabled=not bool(custom_icon_path(icon_key)), key=f"v2_dynamic_remove_{_slug(icon_key)}"):
                    remove_custom_icon(icon_key)
                    st.success("Custom artwork removed.")
                    st.rerun()
        else:
            st.info("Choose or enter an item name to preview its override filename.")

    with tabs[2]:
        st.caption("An icon pack is a ZIP containing a custom_icons folder. It can be moved between installations without touching profiles.")
        export_payload = export_custom_icon_pack()
        st.download_button(
            "Download current icon pack",
            data=export_payload,
            file_name="tower_optimizer_custom_icons.zip",
            mime="application/zip",
            use_container_width=True,
        )
        pack_upload = st.file_uploader("Import icon pack ZIP", type=["zip"], key="v2_icon_pack_upload")
        if st.button("Import icon pack", use_container_width=True, disabled=pack_upload is None, key="v2_icon_pack_import"):
            try:
                result = import_custom_icon_pack(pack_upload.getvalue())
                if result["installed"]:
                    st.success(f"Installed {len(result['installed'])} custom icons.")
                if result["skipped"]:
                    st.warning(f"Skipped {len(result['skipped'])} unsupported files.")
                for error in result["errors"][:12]:
                    st.error(error)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with tabs[3]:
        st.markdown(
            """
            **Recommended files**

            - Transparent PNG or WEBP
            - Square canvas, preferably 256×256 or 512×512
            - Keep the important artwork away from the outer edge
            - Use one image per icon; the app scales it automatically

            **Examples**

            ```text
            data/custom_icons/resources/coins.png
            data/custom_icons/ultimate_weapons/golden_tower.png
            data/custom_icons/relics/<lowercase-hyphenated-relic-name>.png
            data/custom_icons/modules/black-hole-digestor.png
            data/custom_icons/cards/coins.png
            ```

            The public package should ship only artwork that you have permission to redistribute. Exact game images can remain a user-installed local icon pack.
            """
        )


__all__ = [
    "THEMES", "apply_visual_theme", "asset_uri", "render_app_header",
    "render_card_deck_page", "render_icon_studio_page", "render_module_forge_page", "render_overview_page",
    "render_relic_gallery_page", "render_sync_center_page", "render_visual_sidebar",
    "render_grouped_navigation", "NAVIGATION_SECTIONS",
]
