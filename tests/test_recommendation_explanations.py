import json
from pathlib import Path

from tower_optimizer.engines.combined import build_combined_recommendations
from tower_optimizer.explanations import attach_explanations, recommendation_explanation

ROOT = Path(__file__).resolve().parents[1]


def load_profile():
    return json.loads((ROOT / "sample_data" / "example_profile.json").read_text(encoding="utf-8"))


def test_combined_rows_include_structured_explanations():
    profile = load_profile()
    combined = build_combined_recommendations(profile, steps=3)
    rows = combined.get("rows") or []
    assert rows
    top = rows[0]
    explanation = top.get("Explanation")
    assert isinstance(explanation, dict)
    assert explanation.get("Headline")
    assert explanation.get("Why now")
    assert isinstance(explanation["Why now"], list)
    assert explanation["Why now"]
    assert explanation.get("What changes")
    assert explanation.get("Trade-offs")


def test_recommendation_explanation_uses_profile_context():
    profile = load_profile()
    combined = build_combined_recommendations(profile, steps=3)
    row = combined["rows"][0]
    explanation = recommendation_explanation(row, profile, combined.get("analysis"), combined.get("latest_death", ""))
    assert "Why now" in explanation
    assert any("weakest" in item.casefold() or "rank" in item.casefold() for item in explanation["Why now"])
    assert explanation["Inputs"]["Current value"] != "Unknown" or "Unknown" in str(explanation["Trade-offs"])


def test_attach_explanations_preserves_row_fields():
    profile = load_profile()
    combined = build_combined_recommendations(profile, steps=2)
    source = combined["rows"][0]
    enriched = attach_explanations(profile, [source], analysis=combined.get("analysis"), latest_death=combined.get("latest_death", ""))
    assert enriched[0]["Upgrade"] == source["Upgrade"]
    assert "Explanation" in enriched[0]
