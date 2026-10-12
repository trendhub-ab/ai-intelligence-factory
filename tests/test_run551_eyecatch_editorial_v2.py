from __future__ import annotations

import hashlib
import io
import types

from PIL import Image

import run551_eyecatch_editorial_v2 as r551


def test_split_impact_phrase_keeps_japanese_keyword_as_primary_emphasis():
    assert r551.split_impact_phrase("ロボット制御の衝撃") == ("ロボット制御", "の衝撃")
    assert r551.split_impact_phrase("AI運用が変わる") == ("AI運用", "が変わる")


def test_dynamic_badge_changes_with_article_intent():
    assert r551.select_badge(
        "GPT-6 Astraを公開",
        "新しいロボット制御機能が発表された。",
        "ROBOTICS",
    ) == "最新動向を理解"
    assert r551.select_badge(
        "AとBを比較する",
        "どちらを選ぶべきか整理する。",
        "AI & TECH",
    ) == "比較で理解"
    assert r551.select_badge(
        "AIの脆弱性を検証",
        "攻撃リスクと安全性を確認する。",
        "SECURITY",
    ) == "安全性を確認"


def test_sample_layout_restores_badge_hook_title_vertical_rhythm():
    layout = r551.editorial_layout_contract()
    assert layout == {
        "left": 48,
        "badge_top": 140,
        "badge_height": 42,
        "hook_top": 207,
        "title_top": 316,
        "footer_top": 606,
    }
    assert layout["badge_top"] + layout["badge_height"] < layout["hook_top"]
    assert layout["hook_top"] + 44 < layout["title_top"]
    assert layout["title_top"] < layout["footer_top"]


def test_editorial_v2_contract_reserves_one_third_for_visual_and_strengthens_impact_line():
    assert 0.62 <= r551.TEXT_ZONE_RATIO <= 0.68
    assert 0.32 <= r551.VISUAL_ZONE_RATIO <= 0.38
    assert r551.LEAD_TITLE_SCALE <= 0.72
    assert r551.IMPACT_TITLE_SCALE >= 1.10


def test_background_master_contract_uses_user_approved_raster_not_synthetic_visual():
    contract = r551.background_master_contract()
    assert contract == {
        "path": "assets/eyecatch/v2/.background_master_parts",
        "source_size": (1536, 804),
        "target_size": (1280, 670),
        "sha256": "5f1ab5f8ddc807825ad8fa29fdb96b5a165742af73b779223b7fccf8547a77fd",
        "format": "WEBP",
        "part_count": 6,
        "synthetic_visual": False,
        "crop_required": False,
    }


def test_background_master_bytes_are_pinned_and_decode_to_exact_canvas():
    payload = r551._background_master_bytes()
    assert hashlib.sha256(payload).hexdigest() == r551.BACKGROUND_MASTER_SHA256
    with Image.open(io.BytesIO(payload)) as image:
        assert image.format == "WEBP"
        assert image.size == (1280, 670)


def test_synthetic_visual_helpers_are_removed():
    assert not hasattr(r551, "_draw_background_depth")
    assert not hasattr(r551, "_draw_symbolic_ai_flow")
    assert not hasattr(r551, "_draw_industrial_robot_arm")


def test_install_is_zero_api_and_does_not_patch_run180(monkeypatch):
    original_run180_renderer = object()
    original_balanced_renderer = lambda *args, **kwargs: "old"  # noqa: E731

    fake_run180 = types.SimpleNamespace(_render_with_validated_plan=original_run180_renderer)
    fake_run181 = types.SimpleNamespace(_render_balanced_plan=original_balanced_renderer)

    monkeypatch.setitem(__import__("sys").modules, "run180_eyecatch_semantic_layout", fake_run180)
    monkeypatch.setitem(__import__("sys").modules, "run181_eyecatch_visual_balance", fake_run181)

    pipeline = types.SimpleNamespace()
    r551.install(pipeline)

    assert fake_run180._render_with_validated_plan is original_run180_renderer
    assert fake_run181._render_balanced_plan is not original_balanced_renderer
    assert pipeline._RUN551_EYECATCH_EDITORIAL_V2_INSTALLED is True
    assert pipeline.RUN551_EXTRA_PROVIDER_CALLS == 0
    assert pipeline.RUN551_DYNAMIC_BADGE is True
