"""Short in-app explanations: native math vs Effective Paths reference."""
from __future__ import annotations

from typing import Mapping

_HELP: Mapping[str, str] = {
    "recommendation_dashboard": """
**Native math (what drives this page)**  
The shortlist comes from Python engines that compute economy, damage, eHP, and regen upgrade paths from your profile and bundled cost curves. Each path has its own ROI units, so the dashboard **normalizes within a path** and builds a **Priority Index** from rank, relative gain, bottleneck/death weighting, affordability, and model confidence.

**Effective Paths (optional reference only)**  
If you imported a recalculated Effective Paths workbook, its cached paths appear only as a **small tie-break** in the Priority Index. They **do not replace** this list or reorder it to match EP rank #1.

**Where to dig deeper**  
- **Native eEcon / eDamage / eHP / eRegen** — formulas, assumptions, side-by-side regression tables  
- **ROI Paths** — read-only view of imported EP calculated outputs  
- **Calibration Center** — rank-by-rank agreement between native and EP
""".strip(),
    "calibration_center": """
**What this page does**  
Runs the same **native** path engines as the dashboard, then compares each rank to the **imported Effective Paths ROI reference** (cached Excel outputs, not live spreadsheet math).

**Status meanings**  
- **Exact** — same upgrade at that rank  
- **Close** — same upgrade within ±1 rank (aliases handled)  
- **Different** — material mismatch  
- **No reference** — EP had no rows for that path (often missing unlocks, maxed paths, or assist/regen gaps)

**Important**  
Calibration does **not** change recommendations. A low agreement score usually means stale EP, `#NAME?` rows after import, or known native gaps — not that the dashboard is “wrong.” Standalone engines work without any EP import.
""".strip(),
    "whole_account": """
**Native + heuristic layer**  
Whole-account rows extend the combined recommendation engine to cards, modules, relics, bots, guardians, Vault, and similar systems. Lab/coin/stone priorities still come from the **native path engines**; other systems use **verified cost curves where available** and otherwise **strategic heuristics** (labeled in the UI).

**Not Effective Paths**  
This page does not replay EP spreadsheet paths. Import EP only if you want **Calibration Center** or **ROI Paths** for comparison — not to drive these whole-account picks directly.
""".strip(),
    "native_econ": """
**Native math**  
Economy paths (labs, stones, coins, discounts) are computed **in Python** from your profile: workshop/lab levels, GT/BH sync, Death Wave tagging, lab-speed multipliers, and bundled cost curves. Rankings update whenever you change the profile or assumptions in **Model assumptions and controls**.

**Effective Paths reference**  
Regression panels compare native output to an **optional imported EP snapshot**. EP is **not** read at runtime to choose upgrades here.
""".strip(),
    "native_damage": """
**Native math**  
Damage paths use Python formulas and bundled curves from your workshop, labs, keys, and related unlocks. ROI and gain % are **estimated** relative priorities within each resource type (lab / stones / coins / keys).

**Effective Paths reference**  
Side-by-side tables compare against imported EP rows when present. Differences often reflect path naming (e.g. Damage/Meter+ vs Rend Armor+) or EP rows that need a fresh recalc after Master Sheet fill.
""".strip(),
    "native_ehp": """
**Native math**  
eHP paths model lab, coin, and stone upgrades from defense stats, wall health, and bundled curves. **Health stones** currently consider Death Wave saturation; other stone sources may show **no reference** until modeled.

**Effective Paths reference**  
Optional imported paths are for comparison only. Empty EP health-stone tables usually mean EP had nothing to rank, not that native math failed.
""".strip(),
    "native_regen": """
**Native math**  
Regen lab/coin paths use Python models for wall regen and recovery-related upgrades. If recovery labs are at 0 or assist modules are locked, native and EP may both show sparse regen rows.

**Effective Paths reference**  
Imported EP regen paths are cached workbook output. Use **Calibration Center** after recalc to see whether native regen ranks align.
""".strip(),
    "roi_paths": """
**Effective Paths reference (not native)**  
Tables here are **cached calculated outputs** from a filled and **recalculated** Effective Paths `.xlsx` imported under **Import / Export → ROI Reference**. Tower Optimizer does **not** re-run EP formulas in the browser.

**Typical workflow**  
1. Fill **Master Sheet** from your save or profile (tooling or manual)  
2. Open in Excel, force recalc (`Ctrl+Alt+F9`), save  
3. Import the saved workbook as ROI reference  
4. Compare in **Calibration Center** against native engines

**Does not drive the dashboard**  
ROI Paths is a read-only reference layer. **Recommendation Dashboard** rankings come from native math unless you use Calibration to validate alignment.
""".strip(),
    "optimizer": """
**Two layers on one page**  
- **Standalone economy / survival** tables at the top → **native Python** (same engines as Native e* pages)  
- **ROI reference** section below (when imported) → **Effective Paths cached paths**, filtered for Gold Box where possible

Use the top section for day-to-day picks; use the bottom section to inspect what EP calculated at import time.
""".strip(),
    "build_analyzer": """
**Heuristic scores, not ROI paths**  
Build Analyzer scores economy, damage, survivability, and regen **relative to typical milestones** on your account. It suggests review areas and Beast Mode loadout gaps.

**Not native path math or EP**  
These scores do **not** run eEcon/eDamage/eHP engines and do **not** read Effective Paths. For upgrade ROI, use **Recommendation Dashboard** or the **Native e*** pages.
""".strip(),
    "import_roi_reference": """
**Reference import, not profile sync**  
Upload a **recalculated** Effective Paths workbook to cache eEcon, eDamage, eHP, and regen **result tables** for **Calibration Center** and **ROI Paths**.

**Not a substitute for native math**  
Importing ROI reference does **not** overwrite **Recommendation Dashboard** rankings. Native engines always compute recommendations from your profile; EP is for validation and inspection.

**Best results**  
Fill Master Sheet from current save, recalc in Excel, save, then import. Stale or partially broken EP sheets (e.g. `#NAME?` ranks) produce misleading calibration scores.
""".strip(),
}


def render_calculation_help(section: str, *, expanded: bool = False) -> None:
    """Show a collapsible explainer for how native math relates to EP reference."""
    import streamlit as st

    text = _HELP.get(section)
    if not text:
        return
    with st.expander("How are these numbers calculated?", expanded=expanded):
        st.markdown(text)
