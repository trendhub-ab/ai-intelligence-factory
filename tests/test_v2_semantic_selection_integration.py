from __future__ import annotations

from datetime import datetime, timezone

from v2_shadow_selection import ShadowConfig, run_shadow_selection


NOW = datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc)


def _candidate(url: str, *, title: str, description: str):
    return {
        "url": url,
        "title": title,
        "description": description,
        "published_at": "2026-10-16T12:00:00+00:00",
    }


def test_semantic_screening_can_rescue_ai_relevance_before_final_ranking():
    semantic_calls = []
    deep_dive_calls = []

    def provider():
        return [
            _candidate(
                "https://example.com/semantic-winner",
                title="Enterprise platform release",
                description="A new developer platform for model serving, inference deployment, and production automation.",
            ),
            _candidate(
                "https://example.com/literal-ai",
                title="AI update announced",
                description="A general AI update with limited implementation detail.",
            ),
        ]

    def semantic_screen(candidates):
        semantic_calls.append([candidate["candidate_identity"] for candidate in candidates])
        return {
            "https://example.com/semantic-winner": {
                "candidate_identity": "https://example.com/semantic-winner",
                "ai_relevant": True,
                "decision_value": True,
                "change_novelty": True,
                "applied_reader_value": True,
            },
            "https://example.com/literal-ai": {
                "candidate_identity": "https://example.com/literal-ai",
                "ai_relevant": True,
                "decision_value": False,
                "change_novelty": True,
                "applied_reader_value": False,
            },
        }

    def deep_dive(candidate):
        deep_dive_calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": True}

    report = run_shadow_selection(
        providers={"feed": provider},
        semantic_screen=semantic_screen,
        deep_dive=deep_dive,
        config=ShadowConfig(),
        now=NOW,
        run_id="semantic-rescue",
    )

    assert len(semantic_calls) == 1
    assert deep_dive_calls == ["https://example.com/semantic-winner"]
    assert report["screening"][0]["candidate_identity"] == "https://example.com/semantic-winner"
    assert report["screening"][0]["selection_value_score"] == 60
    assert report["screening"][0]["semantic_screening"]["ai_relevant"] is True
    assert report["semantic_screening"]["status"] == "success"
    assert report["actual_calls"]["semantic_screen"] == 1


def test_semantic_provider_failure_falls_back_and_still_runs_evidence_once():
    deep_dive_calls = []

    def semantic_failure(_candidates):
        raise RuntimeError("opaque provider failure")

    def deep_dive(candidate):
        deep_dive_calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": True}

    report = run_shadow_selection(
        providers={
            "feed": lambda: [
                _candidate(
                    "https://example.com/ai-release",
                    title="AI API release",
                    description="New enterprise deployment workflow integration with pricing changes.",
                )
            ]
        },
        semantic_screen=semantic_failure,
        deep_dive=deep_dive,
        config=ShadowConfig(),
        now=NOW,
        run_id="semantic-fallback",
    )

    assert deep_dive_calls == ["https://example.com/ai-release"]
    assert report["v2_selected_candidate_identity"] == "https://example.com/ai-release"
    assert report["semantic_screening"] == {"status": "provider_failure", "fallback_used": True}
    assert report["actual_calls"]["semantic_screen"] == 1
    assert "opaque provider failure" not in str(report)


def test_semantic_invalid_later_result_does_not_partially_boost_earlier_candidate():
    raw_candidates = [
        _candidate(
            "https://example.com/ai-release",
            title="AI API release",
            description="An announced AI API release with specific compatibility information.",
        ),
        _candidate(
            "https://example.com/other",
            title="Industry product announcement",
            description="A general product announcement without verified AI-specific details.",
        ),
    ]

    def run(semantic_screen=None):
        return run_shadow_selection(
            providers={"feed": lambda: list(raw_candidates)},
            semantic_screen=semantic_screen,
            deep_dive=lambda _candidate: {"evidence_sufficient": True},
            config=ShadowConfig(),
            now=NOW,
            run_id="semantic-partial-fallback",
        )

    baseline = run()

    def partly_invalid(_candidates):
        return {
            "https://example.com/ai-release": {
                "candidate_identity": "https://example.com/ai-release",
                "ai_relevant": True,
                "decision_value": True,
                "change_novelty": True,
                "applied_reader_value": True,
            },
            "https://example.com/other": {
                "candidate_identity": "https://example.com/other",
                "ai_relevant": True,
                "decision_value": "invalid",
                "change_novelty": False,
                "applied_reader_value": False,
            },
        }

    failed = run(partly_invalid)

    assert failed["semantic_screening"] == {"status": "provider_failure", "fallback_used": True}
    assert failed["screening"] == baseline["screening"]
    assert failed["v2_selected_candidate_identity"] == baseline["v2_selected_candidate_identity"]


def test_existing_shadow_contract_is_unchanged_when_semantic_screen_is_not_injected():
    report = run_shadow_selection(
        providers={
            "feed": lambda: [
                _candidate(
                    "https://example.com/ai-release",
                    title="AI API release",
                    description="New enterprise deployment workflow integration with pricing changes.",
                )
            ]
        },
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        config=ShadowConfig(),
        now=NOW,
        run_id="semantic-not-configured",
    )

    assert "semantic_screening" not in report
    assert report["actual_calls"] == {"provider": 1, "deep_dive": 1}
