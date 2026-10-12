from __future__ import annotations

import hashlib
import types
from pathlib import Path

import run551_eyecatch_editorial_v2 as r551


def test_split_impact_phrase_keeps_japanese_keyword_as_primary_emphasis():
    assert r551.split_impact_phrase("ロボット制御の衝撃") == ("ロボット制御", "の衝撃")
    assert r551.split_impact_phrase("AI運用が変わる") == ("AI運用", "が変わる")


def test_compose_insight_collapses_badge_and_hook_into_one_reader_line():
    assert r551.compose_insight("結局、何が重要なのか？") == "INSIGHT｜結局、何が重要なのか？"
    assert r551.compose_insight("INSIGHT｜結局、何が重要なのか？") == "INSIGHT｜結局、何が重要なのか？"


def test_editorial_v2_contract_reserves_one_third_for_visual_and_strengthens_impact_line():
    assert 0.62 <= r551.TEXT_ZONE_RATIO <= 0.68
    assert 0.32 <= r551.VISUAL_ZONE_RATIO <= 0.38
    assert r551.LEAD_TITLE_SCALE <= 0.72
    assert r551.IMPACT_TITLE_SCALE >= 1.10


def test_background_master_contract_uses_exact_user_approved_raster_not_synthetic_visual():
    contract = r551.background_master_contract()
    assert contract == {
        "path": "assets/eyecatch/v2/background_master.jpg",
        "source_size": (1536, 804),
        "target_size": (1280, 670),
        "sha256": "adffa620c2323c8a94aadec22149c713e4fee32893df37c444abcd81b1269c34",
        "synthetic_visual": False,
        "crop_required": False,
    }


def test_background_master_bytes_are_pinned_to_approved_image():
    path = Path(r551.__file__).resolve().parent / "assets" / "eyecatch" / "v2" / "background_master.jpg"
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == r551.BACKGROUND_MASTER_SHA256


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
