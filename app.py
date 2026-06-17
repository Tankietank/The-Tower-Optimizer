"""Streamlit launcher for The Tower Optimizer.

Streamlit reruns this launcher whenever a widget changes. Python normally caches
imported modules, so a plain ``from tower_optimizer import application`` only
renders the application on the first run. Reload the application module on
subsequent reruns so navigation and widgets continue to render.
"""

from __future__ import annotations

import importlib
import sys

MODULE_NAME = "tower_optimizer.application"

if MODULE_NAME in sys.modules:
    importlib.reload(sys.modules[MODULE_NAME])
else:
    importlib.import_module(MODULE_NAME)
