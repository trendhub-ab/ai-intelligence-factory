from pathlib import Path

import run180_eyecatch_semantic_layout as run180


ROOT = Path(__file__).resolve().parents[1]


def test_public_eyecatch_never_falls_back_to_discovery_title():
    source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    assert 'parsed.get("title_text", "") or name' not in source


def test_accidental_ellipsis_is_rejected_when_public_title_has_none():
    public_title = "VT Code：AIのコード変更をどう確認する？"
    truncated = "Show HN: VT Code – My attempt at b..."
    plan = {
        "eyecatch_title": truncated,
        "title_lines": ["Show HN: VT Code", "– My attempt at b..."],
        "title_font_size": 60,
        "title_line_gap": 12,
        "subheadline_lines": ["変更確認の仕組みを見る。"],
        "subheadline_font_size": 24,
        "highlight_text": "at b...",
    }
    assert run180._validate_layout_plan(public_title, "変更確認の仕組みを見る。", plan) is None


def test_highlight_rejects_english_fragment():
    title = "VT Code review with AI before merge"
    assert run180._validate_highlight_text(title, [title], "with AI") == ""


def test_highlight_rejects_product_name_only():
    title = "VT Codeでコード変更を確認する"
    assert run180._validate_highlight_text(title, [title], "VT Code") == ""


def test_exact_repair_cannot_hardcode_unproven_legacy_eyecatch_asset():
    source = (ROOT / "run_vtcode_existing_draft_repair.py").read_text(encoding="utf-8")
    assert 'repairs/vtcode_eyecatch_20260927.png' not in source
