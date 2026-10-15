from datetime import datetime, timezone
import inspect

from v2_shadow_selection import ShadowConfig, run_shadow_selection


NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


def test_shadow_report_exposes_only_safe_selection_value_diagnostics():
    signature = inspect.signature(run_shadow_selection)
    forbidden_params = {
        "persist",
        "writer",
        "notion",
        "note",
        "publish",
        "ready_state",
        "economic_state",
        "delivery_ledger",
    }
    assert forbidden_params.isdisjoint(signature.parameters)

    report = run_shadow_selection(
        providers={
            "feed": lambda: [
                {
                    "url": "https://example.com/high-value-ai-change",
                    "title": "AI API launch for enterprise automation",
                    "description": "New pricing and deployment workflow integration for customers.",
                    "published_at": "2026-10-13T12:00:00+00:00",
                }
            ]
        },
        deep_dive=lambda _candidate: {"evidence_sufficient": True},
        config=ShadowConfig(),
        now=NOW,
        run_id="v2-005a-diagnostics",
    )

    screening = report["screening"][0]
    assert isinstance(screening["selection_value_score"], int)
    assert screening["selection_value_score"] == 60
    assert screening["selection_value_reasons"] == [
        "ai_relevance",
        "decision_value",
        "change_novelty",
        "applied_reader_value",
    ]
    assert "description" not in screening
    assert "prompt" not in screening
    assert "provider_response" not in screening
