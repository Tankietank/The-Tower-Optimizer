import json
from pathlib import Path

import pytest

from tower_optimizer.build_archetypes import build_archetype_report
from tower_optimizer.playbook_export import (
    build_playbook_html,
    build_playbook_pdf_bytes,
    format_playbook_markdown,
    format_playbook_plaintext,
    playbook_export_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def load_profile():
    return json.loads((ROOT / "sample_data" / "example_profile.json").read_text(encoding="utf-8"))


def _sample_report():
    return build_archetype_report(load_profile(), "tournament_specialist", steps=3, top_n=5)


def test_playbook_markdown_includes_core_sections():
    report = _sample_report()
    text = format_playbook_markdown(report, profile_name="test_profile")
    assert "Beast Mode Playbook" in text
    assert "test_profile" in text
    assert "Master checklist" in text
    assert "Sub-effect reroll targets" in text
    assert "Ultimate Weapons" in text
    assert report["label"] in text


def test_playbook_plaintext_strips_markdown():
    report = _sample_report()
    plain = format_playbook_plaintext(report)
    assert "**" not in plain
    assert "# " not in plain.splitlines()[0]


def test_playbook_html_is_valid_document():
    report = _sample_report()
    html = build_playbook_html(report)
    assert "<html" in html.lower()
    assert report["label"] in html


def test_playbook_export_bundle_filenames():
    report = _sample_report()
    bundle = playbook_export_bundle(report, profile_name="demo")
    assert bundle["markdown"]
    assert bundle["plaintext"]
    assert bundle["html"]
    assert bundle["filenames"]["markdown"].endswith(".md")
    assert bundle["filenames"]["pdf"].endswith(".pdf")
    if bundle.get("pdf") is not None:
        assert bundle["pdf"].startswith(b"%PDF")


def test_playbook_pdf_bytes_non_empty():
    fpdf = pytest.importorskip("fpdf")
    report = _sample_report()
    pdf_bytes = build_playbook_pdf_bytes(report)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 200
