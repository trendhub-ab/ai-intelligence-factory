from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import local_skills_daily_canary as daily_canary
import production_pipeline
import pipeline
from local_skills.production_canary import apply_to_production_parsed, build_snapshot
from local_skills.evidence_boundary import apply_evidence_boundary


ROOT = Path(__file__).resolve().parents[1]


def _parsed() -> dict:
    return {
        "title_text": "PROVIDER ARTICLE TITLE MUST BE DISCARDED",
        "note_draft": "THIS PROVIDER ARTICLE BODY MUST BE DISCARDED",
        "score": 62,
        "decision_text": "WATCH",
        "decision_reason_text": "The measured result is useful but workload transfer is unverified.",
        "source_summary_text": "A benchmark example measured a 7x faster kernel on a fixed workload.",
        "what_text": "A kernel implementation evaluated with a benchmark example.",
        "why_important_text": "It provides a bounded engineering result that can be reproduced.",
        "why_not_important_text": "PROVIDER ARTICLE RISK MUST NOT LEAK",
        "who_should_use_text": "PROVIDER ARTICLE BEST FOR MUST NOT LEAK",
        "who_should_not_use_text": "PROVIDER ARTICLE AVOID FOR MUST NOT LEAK",
        "main_risk_text": "",
        "best_for_text": "",
        "avoid_for_text": "",
        "action_text": "Reproduce the benchmark on one internal workload.",
        "score_breakdown_text": "",
        "paradigm_shift_text": "",
        "alternative_comparison_text": "",
        "migration_cost_text": "",
        "future_scenario_text": "",
    }


def _repo() -> dict:
    return {
        "nameWithOwner": "Fresh benchmark candidate",
        "url": "https://example.invalid/fresh",
        "primaryUrl": "https://example.invalid/fresh",
        "source": "HackerNews",
    }


def test_production_adapter_discards_all_provider_article_surfaces():
    original = _parsed()
    out, meta = apply_to_production_parsed(
        _repo(),
        original,
        source="HackerNews",
        primary_url="https://example.invalid/fresh",
        grounding={"evidence_urls": ["https://example.invalid/fresh"]},
        evidence_context="A benchmark example measured a 7x faster kernel on a fixed workload.",
    )

    assert original["note_draft"] == "THIS PROVIDER ARTICLE BODY MUST BE DISCARDED"
    assert out["note_draft"] != original["note_draft"]
    for forbidden in (
        "THIS PROVIDER ARTICLE BODY MUST BE DISCARDED",
        "PROVIDER ARTICLE TITLE MUST BE DISCARDED",
        "PROVIDER ARTICLE RISK MUST NOT LEAK",
        "PROVIDER ARTICLE BEST FOR MUST NOT LEAK",
        "PROVIDER ARTICLE AVOID FOR MUST NOT LEAK",
    ):
        assert forbidden not in out["note_draft"]
        assert forbidden not in out["title_text"]

    assert out["decision_text"] == original["decision_text"]
    assert out["score"] == original["score"]
    assert meta["provider_article_surface_reused"] is False
    assert meta["deterministic_title"] is True
    assert meta["completeness_adapter_fallback_fields"] == [
        "avoid_for", "best_for", "primary_risk"
    ]
    assert meta["writer_blob_sha"] == "204cce30ab838e0d6dac9cbe762d0a82ff02f1aa"
    assert meta["canonicalizer_blob_sha"] == "414089a14c238f104b2866507ddf8521c2baf420"
    assert meta["evidence_boundary_version"] == "stage8-v4"
    assert meta["removed_unsupported_numeric_claims"] == 0



def test_production_adapter_syncs_canonicalized_action_for_human_appeal_gate():
    parsed = _parsed()
    parsed["score"] = 56
    parsed["decision_text"] = "WATCH"
    parsed["action_text"] = "検証結果を注視します。"

    out, meta = apply_to_production_parsed(
        _repo(),
        parsed,
        source="HackerNews",
        primary_url="https://example.invalid/fresh",
        grounding={"evidence_urls": ["https://example.invalid/fresh"]},
        evidence_context="The source supports a bounded verification-only decision.",
    )

    assert out["action_text"].startswith("限定的な検証として、")
    assert out["action_text"] in out["note_draft"]
    _state, issues = pipeline.validate_human_appeal_gate(out)
    assert "action_collapsed_to_generic_monitoring" not in issues
    assert meta["compiled_structured_surface_synced"] is True


def test_evidence_boundary_removes_unsupported_vague_temporal_claim():
    snapshot = {
        "source_summary": "一次情報の範囲です。",
        "what": "出来事を確認しました。",
        "why_important": "実態把握に数ヶ月を要するほど難しいとされています。",
        "decision_reason": "追加確認が必要です。",
        "action": "小さな検証に限定します。",
        "primary_risk": "一般化しないことです。",
        "best_for": "限定検証するチーム。",
        "avoid_for": "すぐ本番適用したいチーム。",
    }
    bounded, meta = apply_evidence_boundary(snapshot, "The source does not state a duration.")
    assert "数ヶ月" not in bounded["why_important"]
    assert meta["removed_count"] == 1
    assert meta["removed_unsupported_numeric_claims"][0]["claim"] == "数ヶ月"


def test_evidence_boundary_preserves_supported_vague_temporal_claim():
    snapshot = {
        "source_summary": "一次情報の範囲です。",
        "what": "出来事を確認しました。",
        "why_important": "実態把握に数ヶ月を要したとされています。",
        "decision_reason": "追加確認が必要です。",
        "action": "小さな検証に限定します。",
        "primary_risk": "一般化しないことです。",
        "best_for": "限定検証するチーム。",
        "avoid_for": "すぐ本番適用したいチーム。",
    }
    bounded, meta = apply_evidence_boundary(snapshot, "The investigation took several months.")
    assert "数ヶ月" in bounded["why_important"]
    assert meta["removed_count"] == 0


def test_completeness_adapter_prefers_management_only_values_when_present():
    parsed = _parsed()
    parsed.update({
        "main_risk_text": "Management risk.",
        "best_for_text": "Management best.",
        "avoid_for_text": "Management avoid.",
    })
    snapshot = build_snapshot(
        _repo(),
        parsed,
        source="HackerNews",
        primary_url="https://example.invalid/fresh",
        grounding={"evidence_urls": ["https://example.invalid/fresh"]},
    )
    assert snapshot["primary_risk"] == "Management risk."
    assert snapshot["best_for"] == "Management best."
    assert snapshot["avoid_for"] == "Management avoid."
    assert snapshot["reader_title"].startswith("Fresh benchmark candidate")
    assert "PROVIDER ARTICLE TITLE MUST BE DISCARDED" not in snapshot["reader_title"]


def test_observed_canary_records_are_excluded_from_later_fresh_measurements():
    assert daily_canary._already_observed({
        "nameWithOwner": "LLM Agents Can Easily Tamper With Their Own Traces",
        "url": "https://arxiv.org/abs/2609.30266",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "different title",
        "url": "https://arxiv.org/abs/2609.30266v1",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "U.S. appeals court upholds designation of Anthropic as supply chain risk",
        "url": "https://example.invalid/news",
    })

    assert daily_canary._already_observed({
        "nameWithOwner": "My coding agent pushed a commit deleting every file on main",
        "url": "https://dev.karakun.com/2026/08/28/coding-agent-pushed-deletion-to-main.html",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "Jevmem – automatic project memory for Claude Code, built on Jev",
        "url": "https://github.com/Avinash-jetwani/jevmem",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "Build Plugins for Claude",
        "url": "https://claude.com/blog/build-plugins-for-claude",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "Yes, Claude can do nine loops",
        "url": "https://www.anthropic.com/research/yes-claude-can-do-nine-loops",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "DeepSeek beats GPT-6 Sol in autonomous drug development",
        "url": "https://eval.raycaster.ai/benchmarks/biopharma-bench/",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "Show HN: I couldn't deal with another Claude Code tab",
        "url": "https://aidash.dev/",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure",
        "url": "https://arxiv.org/abs/2609.30217v1",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "Minimally Invasive Steering of Language Models",
        "url": "https://arxiv.org/abs/2609.30248v1",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "PoEM: Predicting RL Outcomes from Existing Policies",
        "url": "https://arxiv.org/abs/2609.30226v1",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "OpenAI says agents leaked 53 images from ChatGPT users",
        "url": "https://www.theguardian.com/technology/2026/sep/25/openai-agents-leaked-53-images-chatgpt",
    })
    assert not daily_canary._already_observed(_repo())



def test_run147_contaminated_holdout_is_excluded():
    assert daily_canary._already_observed({
        "nameWithOwner": "Requirement-Bound Verified Commissioning: A Frozen Four-Billion-Parameter Local Model as a Candidate Generator under an External Acceptance Layer with Verification and Release Authority",
        "url": "https://arxiv.org/abs/2609.30219v1",
    })


def test_deep_dive_attempt_counter_ignores_screening_and_calibration():
    pipeline = SimpleNamespace(
        GEMINI_USAGE_AUDIT=SimpleNamespace(records=[
            {"kind": "screening_batch"},
            {"kind": "global_calibration"},
            {"kind": "deep_dive"},
            {"kind": "screening_batch"},
        ])
    )
    assert daily_canary._deep_dive_attempt_count(pipeline) == 1


def test_canary_is_an_explicit_one_shot_mode():
    assert "local_skills_canary_validation" in production_pipeline._ONE_SHOT_MODES


def test_workflow_canary_is_measurement_only_and_never_fans_out():
    workflow = (ROOT / ".github" / "workflows" / "daily-one-shot.yml").read_text(encoding="utf-8")
    assert "- local_skills_canary_validation" in workflow
    assert "AIIF_LOCAL_SKILLS_CANARY:" in workflow
    assert "Local Skills fresh canary is measurement-only: downstream synchronization skipped." in workflow
    assert "if: ${{ inputs.mode != 'local_skills_canary_validation' }}" in workflow
    assert "ref: main" in workflow
    assert "if: ${{ inputs.mode == 'local_skills_canary_validation' }}" in workflow
    assert "ref: ${{ github.ref_name }}" in workflow


def test_pipeline_canary_fails_closed_on_persistence_attempt():
    source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    assert 'if local_skills_canary and persist_results:' in source
    assert 'Local Skills canary is measurement-only and forbids Production persistence' in source
    assert 'Local Skills canary forbids provider quality retries' in source
    assert 'source_info.get("verification_context")' in source
    assert 'evidence_context=(' in source
    assert 'local_skills_canary_skip_eyecatch' in source
    assert 'must not spend eyecatch provider quota' in source


def test_canary_runner_disables_rewrite_rescue_and_second_deep_dive():
    source = (ROOT / "local_skills_daily_canary.py").read_text(encoding="utf-8")
    assert "pipeline.MAX_QUALITY_RETRIES = 0" in source
    assert "pipeline.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = False" in source
    assert "persist_results=False" in source
    assert 'result["outcome"] not in {"accepted", "rejected"}' in source
    assert "OBSERVED_CANARY_NAMES" in source
    assert "pre_deep_dive_backfill" in source
    assert "deep_dive_without_measurement" in source
    assert "after_deep_dive > before_deep_dive" in source


def test_v433_observed_candidates_are_excluded():
    assert daily_canary._already_observed({
        "nameWithOwner": "AD-WM: Action-Discriminative World Models for Counterfactual Model Predictive Control",
        "url": "https://arxiv.org/abs/2609.30264v1",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "The same bug fix costs 0.4¢ or $2, depending on which coding agent you ask",
        "url": "https://www.ariwilson.com/writing/bakeoff-results/",
    })
