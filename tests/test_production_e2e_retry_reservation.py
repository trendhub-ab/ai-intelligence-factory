from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "production-e2e-retry-20260924.yml"


def test_retry_reservation_has_two_exact_jst_firing_opportunities():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "cron: '5 8 24 9 *'" in text
    assert "cron: '15 8 24 9 *'" in text
    assert '$(date -u +%F)" = "2026-09-24"' in text


def test_retry_reservation_never_runs_production_directly_or_receives_model_secrets():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python production_pipeline.py" not in text
    assert "GEMINI_API_KEY:" not in text
    assert "NOTION_API_KEY:" not in text
    assert "GOOGLE_API_KEY:" not in text
    assert "gh workflow run daily-one-shot.yml" in text
    assert "-f mode=production_e2e_validation" in text
    assert "-f confirm=RUN_ONCE" in text


def test_backup_suppresses_duplicate_only_after_prior_successful_reservation():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '.conclusion == \\"success\\"' in text
    assert 'steps.prior.outputs.skip == \'false\'' in text
    assert "Prior successful reservation run found" in text


def test_reservation_verifies_new_one_shot_before_it_can_count_as_success():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "BEFORE_ID:" in text
    assert "Verify a new ONE-SHOT run actually exists" in text
    assert "no new ONE-SHOT run was observed" in text
    assert "Verified new Production E2E ONE-SHOT run" in text
