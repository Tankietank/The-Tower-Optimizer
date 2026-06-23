from tower_optimizer.calculation_help import _HELP


def test_calculation_help_sections_cover_key_pages():
    expected = {
        "recommendation_dashboard",
        "calibration_center",
        "whole_account",
        "native_econ",
        "native_damage",
        "native_ehp",
        "native_regen",
        "roi_paths",
        "optimizer",
        "build_analyzer",
        "import_roi_reference",
    }
    assert expected <= set(_HELP.keys())
    for section in expected:
        text = _HELP[section]
        assert "Effective Paths" in text or "EP" in text
        assert "native" in text.casefold()
