"""Streamlit launcher for The Tower Optimizer.

Streamlit reruns this launcher whenever a widget changes. Python normally caches
imported modules, so a plain ``from tower_optimizer import application`` only
renders the application on the first run. Reload the application module on
subsequent reruns so navigation and widgets continue to render.
"""

from __future__ import annotations

import importlib
import sys
import traceback

import streamlit as st

MODULE_NAME = "tower_optimizer.application"


def _render_import_error(exc: BaseException) -> None:
    st.set_page_config(page_title="Tower Optimizer — Error", layout="wide")
    st.error("Tower Optimizer hit an error while loading.")
    st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), language="text")
    st.info(
        "If this happened right after importing IDS/EP workbooks, try restarting the container, "
        "then load your saved profile from the sidebar. Large Effective Paths imports can take "
        "1–2 minutes and need the `/app/data` volume mounted in Docker."
    )


try:
    if MODULE_NAME in sys.modules:
        importlib.reload(sys.modules[MODULE_NAME])
    else:
        importlib.import_module(MODULE_NAME)
except Exception as exc:  # pragma: no cover - Streamlit UI fallback
    _render_import_error(exc)
