from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "production-e2e-retry-20260924.yml"
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
REFERENCE_GUARD = ROOT / "workflow_reference_guard.py"


def test_consumed_dated_retry_reservation_is_retired():
    assert not WORKFLOW.exists(), "consumed dated cron reservation must not remain executable"


def test_daily_one_shot_remains_explicit_only():
    text = ONE_SHOT.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "\n  schedule:" not in text
    assert "\n  push:" not in text
    assert "confirm == 'RUN_ONCE'" in text


def test_repository_guard_rejects_fixed_schedule_triggers():
    text = REFERENCE_GUARD.read_text(encoding="utf-8")
    assert "fixed schedule trigger is forbidden" in text
