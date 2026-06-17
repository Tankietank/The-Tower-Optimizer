"""Navigation model for the Tower Optimizer interface.

The navigation data is kept independent from Streamlit so tests can verify that
all application pages are reachable and that no page appears in two sections.
"""
from __future__ import annotations

from typing import Iterable

NAVIGATION_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("🏠 Home", ("Overview 2.0", "Dashboard")),
    ("✨ Visual Tools", ("Sync Center", "Card Deck", "Module Forge", "Relic Gallery", "Icon Studio")),
    ("🎯 Optimize", ("Recommendation Dashboard", "Whole Account", "Progression Planner", "Optimizer", "Build Analyzer", "ROI Paths")),
    ("📈 Performance", ("Battle Reports", "Battle Learning", "Build Audit", "Calibration Center", "Native eEcon", "Native eDamage", "Native eHP", "Native eRegen")),
    ("🧱 Build & Collection", ("Player", "Workshop", "Labs", "Enhancements", "Ultimate Weapons", "Modules", "Cards", "Relics", "Themes & Songs", "Bots", "Guardians", "Vault")),
    ("👤 Profile & Data", ("Setup Wizard", "Profile Setup", "Import / Export", "Profile Completeness", "Data Quality", "Game Data", "Raw Profile")),
    ("⚙️ System", ("System & Updates",)),
)


def navigation_pages(sections: Iterable[tuple[str, Iterable[str]]] = NAVIGATION_SECTIONS) -> tuple[str, ...]:
    """Return all page names in display order."""
    return tuple(page for _section, pages in sections for page in pages)


def section_for_page(page_name: str) -> str | None:
    """Return the display section containing *page_name*, if any."""
    for section, pages in NAVIGATION_SECTIONS:
        if page_name in pages:
            return section
    return None


__all__ = ["NAVIGATION_SECTIONS", "navigation_pages", "section_for_page"]
