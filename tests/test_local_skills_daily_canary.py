from __future__ import annotations

from pathlib import Path

import production_pipeline
from local_skills.production_canary import apply_to_production_parsed


ROOT = Path(__file__).resolve().parents[1]


def _parsed() -> dict:
    return {
        "title_text": "Measured kernel benchmark",
        "note_draft": "THIS PROVIDER ARTICLE BODY MUST BE DISCARDED",
        "score": 62,
        "decision_text": "WATCH",
        "decision_reason_text": "The measured result is useful but workload transfer is unverified.",
        "source_summary_text": "A benchmark example measured a 7x faster kernel on a fixed workload.",
        "what_text": "A kernel implementation evaluated with a benchmark example.",
        "why_important_text": "It provides a bounded engineering result that can be reproduced.",
        "why_not_important_text": "The result may change on another workload or execution environment.",
        "who_should_use_text": "Teams that can reproduce kernel benchmarks.",
        "who_should_not_use_text": "Teams that require a universal performance guarantee.",
        "action_text": "Reproduce the benchmark on one internal workload.",
        "score_breakdown_text": "",
        "paradigm_shift_text": "",
        "alternative_comparison_text": "",
        "migration_cost_text": "",
        "future_scenario_text": "",
    }


def test_production_adapter_discards_provider_article_body():
    repo = {
        "nameWithOwner": "Fresh benchmark candidate",
        "url": "https://example.invalid/fresh",
        "primaryUrl": "https://example.invalid/fresh",
        "source": "HackerNews",
    }
    original = _parsed()
    out, meta = apply_to_production_parsed(
        repo,
        original,
        source="HackerNews",
        primary_url="https://example.invalid/fresh",
        grounding={"evidence_urls": ["https://example.invalid/fresh"]},
    )

    assert original["note_draft"] == "THIS PROVIDER ARTICLE BODY MUST BE DISCARDED"
    assert out["note_draft"] != original["note_draft"]
    assert "THIS PROVIDER ARTICLE BODY MUST BE DISCARDED" not in out["note_draft"]
    assert out["decision_text"] == original["decision_text"]
    assert out["score"] == original["score"]
    assert meta["writer_blob_sha"] == "dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2"
    assert meta["canonicalizer_blob_sha"] == "414089a14c238f104b2866507ddf8521c2baf420"


def test_canary_is_an_explicit_one_shot_mode():
    assert "local_skills_canary_validation" in production_pipeline._ONE_SHOT_MODES


def test_workflow_canary_is_measurement_only_and_never_fans_out():
    workflow = (ROOT / ".github" / "workflows" / "daily-one-shot.yml").read_text(encoding="utf-8")
    assert "- local_skills_canary_validation" in workflow
    assert "AIIF_LOCAL_SKILLS_CANARY:" in workflow
    assert "Local Skills fresh canary is measurement-only: downstream synchronization skipped." in workflow
    assert "inputs.mode == 'local_skills_canary_validation' && github.ref_name || 'main'" in workflow


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
