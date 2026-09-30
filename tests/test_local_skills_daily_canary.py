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
    assert meta["writer_blob_sha"] == "884c550125ff563b2d8bcf20132f3373d332f28d"
    assert meta["canonicalizer_blob_sha"] == "93a62ef2311d43dc1cb84fa5affe9d798a133021"
    assert meta["evidence_boundary_version"] == "stage10-v4"
    assert meta["integration_version"] == "v4.3.9-integrated"
    assert meta["publication_topic_fit_version"] == "local-v1"
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


def test_fresh_canary_uses_current_production_acquisition_breadth():
    p = SimpleNamespace(
        GITHUB_FETCH_LIMIT=50,
        HN_FETCH_LIMIT=50,
        ARXIV_FETCH_LIMIT=50,
        OFFICIAL_VENDOR_FETCH_LIMIT=50,
        MAX_SCREENING_CANDIDATES=200,
    )
    limits = daily_canary._production_acquisition_limits(p)
    assert limits == {
        "GitHub": 50,
        "HackerNews": 50,
        "ArXiv": 50,
        "OfficialVendor": 50,
        "max_screening": 200,
    }


def test_fresh_canary_acquisition_limit_fallbacks_remain_bounded():
    limits = daily_canary._production_acquisition_limits(SimpleNamespace())
    assert limits["GitHub"] == daily_canary.FALLBACK_FETCH_PER_SOURCE
    assert limits["HackerNews"] == daily_canary.FALLBACK_FETCH_PER_SOURCE
    assert limits["ArXiv"] == daily_canary.FALLBACK_FETCH_PER_SOURCE
    assert limits["OfficialVendor"] == daily_canary.FALLBACK_FETCH_PER_SOURCE
    assert limits["max_screening"] == daily_canary.FALLBACK_MAX_SCREENING



def test_source_stratified_fresh_rejects_invalid_targets(monkeypatch):
    for source in ("github", "ProductHunt", "GitHub ", "../OfficialVendor"):
        monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", source)
        try:
            daily_canary._validated_requested_source()
        except RuntimeError as exc:
            assert "Invalid source-stratified Fresh target" in str(exc)
        else:
            raise AssertionError(f"Unsafe source passed: {source!r}")


def test_source_stratified_fresh_keeps_only_requested_source(monkeypatch):
    repos = [
        {"source": "HackerNews", "url": "https://example.net/hn"},
        {"source": "GitHub", "url": "https://example.net/gh"},
        {"source": "ArXiv", "url": "https://example.net/arxiv"},
        {"source": "OfficialVendor", "url": "https://example.net/vendor"},
    ]
    for source in sorted(daily_canary.STRATIFIED_SOURCES):
        monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", source)
        assert daily_canary._validated_requested_source() == source
        assert daily_canary._restrict_source(repos, source) == [
            row for row in repos if row["source"] == source
        ]


def test_source_stratification_has_no_effect_when_omitted(monkeypatch):
    monkeypatch.delenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", raising=False)
    repos = [{"source": "GitHub"}, {"source": "HackerNews"}]
    assert daily_canary._validated_requested_source() == ""
    assert daily_canary._restrict_source(repos, "") == repos


def test_v439_source_stratified_hn_holdout_is_not_fresh_again():
    assert daily_canary._already_observed({
        "nameWithOwner": "Inspect: An open-source framework for large language model evaluations",
        "source": "HackerNews",
        "url": "https://inspect.aisi.org.uk/",
    })
    assert daily_canary._already_observed({
        "nameWithOwner": "A different name for the same audited source",
        "source": "HackerNews",
        "primaryUrl": "https://inspect.aisi.org.uk/",
    })


def test_source_attrition_counts_keep_four_distinct_routes():
    rows = [{"source": "GitHub"}, {"source": "GitHub"},
            {"source": "HackerNews"}, {"source": "ArXiv"},
            {"source": "OfficialVendor"}, {"source": "unknown"}]
    assert daily_canary._source_counts(rows) == {
        "ArXiv": 1, "GitHub": 2, "HackerNews": 1, "OfficialVendor": 1,
    }
    assert all(value == 0 for value in daily_canary._source_counts([]).values())


def test_screening_diagnostics_are_observational_only():
    items = [{"score": 41}, {"score": 61}, {"score": 82}]
    original = [dict(item) for item in items]
    result = daily_canary._screening_diagnostics(
        items, SimpleNamespace(NOTION_SAVE_THRESHOLD_SCORE=65))
    assert result == {
        "screened_count": 3,
        "max_score": 82,
        "notion_save_threshold": 65,
        "at_or_above_notion_save": 1,
    }
    assert items == original
    assert daily_canary._screening_diagnostics(
        [], SimpleNamespace(NOTION_SAVE_THRESHOLD_SCORE=65))["max_score"] is None


def test_fresh_dedupe_diagnostics_separate_existing_and_intra_run(monkeypatch):
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "GitHub")
    rows = [
        {"nameWithOwner": "already stored", "source": "GitHub", "url": "https://example.test/old"},
        {"nameWithOwner": "fresh a", "source": "GitHub", "url": "https://example.test/new"},
        {"nameWithOwner": "fresh b", "source": "GitHub", "url": "https://example.test/new"},
    ]
    mock = SimpleNamespace(
        fetch_github_trending=lambda n: rows,
        fetch_hackernews_top=lambda n: [],
        fetch_arxiv_ai_ml=lambda n: [],
        fetch_producthunt_trending=lambda n: [],
        round_robin_candidates=lambda groups, limit: groups["GitHub"][:limit],
        legal_safety_gate=lambda repo: (True, ""),
        get_existing_repo_urls=lambda: {"https://example.test/old"},
        candidate_identity_urls=lambda repo: {repo["url"]},
        _normalize_title_for_match=lambda title: title.lower(),
    )
    fresh, diag = daily_canary._fresh_candidates(mock)
    assert [r["nameWithOwner"] for r in fresh] == ["fresh a"]
    breakdown = diag["source_attrition"]
    assert breakdown["dedupe_excluded_by_source"]["GitHub"] == 2
    assert breakdown["existing_notion_duplicate_by_source"]["GitHub"] == 1
    assert breakdown["intra_run_duplicate_by_source"]["GitHub"] == 1
    assert breakdown["fresh_by_source"]["GitHub"] == 1


def test_github_run202_attrition_replay_stops_before_any_model_calls(monkeypatch):
    """Offline synthetic replay of observed counts, not a new Fresh measurement."""
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "GitHub")
    rows = [
        {
            "source": "GitHub",
            "nameWithOwner": f"synthetic-fresh-audit-{index}",
            "url": f"https://example.invalid/github-audit-{index:02d}",
        }
        for index in range(50)
    ]
    existing = {row["url"] for row in rows[17:]}
    log = []
    captured = []

    def forbidden(*args, **kwargs):
        raise AssertionError("zero-fresh diagnosis must not invoke any model")

    mock = SimpleNamespace(
        fetch_github_trending=lambda n: rows[:n],
        fetch_hackernews_top=lambda n: [],
        fetch_arxiv_ai_ml=lambda n: [],
        fetch_producthunt_trending=lambda n: [],
        round_robin_candidates=lambda groups, limit: groups["GitHub"][:limit],
        legal_safety_gate=lambda row: (
            int(row["url"][-2:]) >= 17,
            "synthetic unsafe" if int(row["url"][-2:]) < 17 else "",
        ),
        get_existing_repo_urls=lambda: existing,
        candidate_identity_urls=lambda row: {row["url"]},
        _normalize_title_for_match=lambda title: title.casefold(),
        initialize_runtime=lambda: log.append("init"),
        reset_article_style_memory=lambda: log.append("reset"),
        screen_candidates_in_batches=forbidden,
        calibrate_candidates=forbidden,
        generate_intelligence_report=forbidden,
        MAX_QUALITY_RETRIES=2,
        ENABLE_DETERMINISTIC_PUBLICATION_RESCUE=True,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(daily_canary, "_write", lambda result: captured.append(result.copy()))
    try:
        daily_canary.run(mock)
    except RuntimeError as exc:
        assert "No fresh Daily candidate" in str(exc)
    else:
        raise AssertionError("The synthetic 0-fresh run must stop before Screening")
    assert log == ["init", "reset"]
    assert mock.MAX_QUALITY_RETRIES == 2
    assert mock.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE is True
    assert len(captured) == 1
    report = captured[0]
    assert report["screening_candidates"] == 0
    assert report["local_skills_additional_provider_calls"] == 0
    attr = report["acquisition"]["source_attrition"]
    assert attr["collected_by_source"]["GitHub"] == 50
    assert attr["legal_safe_by_source"]["GitHub"] == 33
    assert attr["dedupe_excluded_by_source"]["GitHub"] == 33
    assert attr["existing_notion_duplicate_by_source"]["GitHub"] == 33
    assert attr["intra_run_duplicate_by_source"]["GitHub"] == 0
    assert attr["fresh_by_source"]["GitHub"] == 0


def test_invalid_source_is_rejected_before_runtime_initialization(monkeypatch):
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "github ")
    touched = []
    mock = SimpleNamespace(initialize_runtime=lambda: touched.append("runtime"))
    try:
        daily_canary.run(mock)
    except RuntimeError as exc:
        assert "Invalid source-stratified Fresh target" in str(exc)
    else:
        raise AssertionError("Invalid source must fail before runtime init")
    assert touched == []


def test_cross_source_duplicate_is_measured_but_source_order_is_unchanged(monkeypatch):
    """Document a selection-protocol limitation without modifying it."""
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "GitHub")
    shared = "https://example.invalid/one-primary"
    hn = {"source": "HackerNews", "nameWithOwner": "HN mirror", "url": shared}
    gh = {"source": "GitHub", "nameWithOwner": "GH repo", "url": shared}
    mock = SimpleNamespace(
        fetch_github_trending=lambda n: [gh],
        fetch_hackernews_top=lambda n: [hn],
        fetch_arxiv_ai_ml=lambda n: [],
        fetch_producthunt_trending=lambda n: [],
        round_robin_candidates=lambda groups, limit: [
            groups["HackerNews"][0], groups["GitHub"][0],
        ][:limit],
        legal_safety_gate=lambda row: (True, ""),
        get_existing_repo_urls=lambda: set(),
        candidate_identity_urls=lambda row: {row["url"]},
        _normalize_title_for_match=lambda name: name.casefold(),
    )
    repos, result = daily_canary._fresh_candidates(mock)
    assert repos == []
    attr = result["source_attrition"]
    assert attr["existing_notion_duplicate_by_source"]["GitHub"] == 0
    assert attr["intra_run_duplicate_by_source"]["GitHub"] == 1
    assert attr["fresh_by_source"]["HackerNews"] == 1
    assert attr["fresh_by_source"]["GitHub"] == 0
    # This is a known protocol order, not evidence of GitHub candidate quality.


def test_duplicate_reason_counters_may_overlap_but_aggregate_is_a_union(monkeypatch):
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "GitHub")
    first = {
        "source": "GitHub", "nameWithOwner": "new",
        "url": "https://example.invalid/fresh",
    }
    second = {
        "source": "GitHub", "nameWithOwner": "both",
        "url": "https://example.invalid/old",
    }
    mock = SimpleNamespace(
        fetch_github_trending=lambda n: [first, second],
        fetch_hackernews_top=lambda n: [],
        fetch_arxiv_ai_ml=lambda n: [],
        fetch_producthunt_trending=lambda n: [],
        round_robin_candidates=lambda groups, limit: groups["GitHub"][:limit],
        legal_safety_gate=lambda row: (True, ""),
        get_existing_repo_urls=lambda: {"https://example.invalid/old"},
        candidate_identity_urls=lambda row: (
            {row["url"], "https://example.invalid/fresh"}
            if row is second else {row["url"]}
        ),
        _normalize_title_for_match=lambda name: name.casefold(),
    )
    fresh, report = daily_canary._fresh_candidates(mock)
    assert [row["nameWithOwner"] for row in fresh] == ["new"]
    a = report["source_attrition"]
    assert a["dedupe_excluded_by_source"]["GitHub"] == 1
    assert a["existing_notion_duplicate_by_source"]["GitHub"] == 1
    assert a["intra_run_duplicate_by_source"]["GitHub"] == 1
