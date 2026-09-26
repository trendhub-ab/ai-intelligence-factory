from __future__ import annotations

from pathlib import Path

import local_skills_daily_canary as daily_canary
import production_pipeline
from local_skills.production_canary import apply_to_production_parsed, build_snapshot


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
        # These three fields may be article-body fallbacks in the Production parser.
        # The Local Skills adapter must ignore them.
        "why_not_important_text": "PROVIDER ARTICLE RISK MUST NOT LEAK",
        "who_should_use_text": "PROVIDER ARTICLE BEST FOR MUST NOT LEAK",
        "who_should_not_use_text": "PROVIDER ARTICLE AVOID FOR MUST NOT LEAK",
        # Management-only legacy fields are intentionally absent, matching the
        # current eight-field Free Article management contract.
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
    assert meta["writer_blob_sha"] == "dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2"
    assert meta["canonicalizer_blob_sha"] == "414089a14c238f104b2866507ddf8521c2baf420"


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


def test_first_observed_canary_record_is_excluded_from_next_fresh_measurement():
    assert daily_canary._already_observed({
        "nameWithOwner": "LLM Agents Can Easily Tamper With Their Own Traces",
        "url": "https://arxiv.org/abs/2609.30266",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "different title",
        "url": "https://arxiv.org/abs/2609.30266v1",
    })
    assert not daily_canary._already_observed(_repo())


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


def test_canary_runner_disables_rewrite_and_rescue_for_measurement():
    source = (ROOT / "local_skills_daily_canary.py").read_text(encoding="utf-8")
    assert "pipeline.MAX_QUALITY_RETRIES = 0" in source
    assert "pipeline.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = False" in source
    assert "persist_results=False" in source
    assert 'result["outcome"] not in {"accepted", "rejected"}' in source
    assert "OBSERVED_CANARY_NAMES" in source
