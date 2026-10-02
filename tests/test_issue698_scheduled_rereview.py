from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "issue698-scheduled-rereview.yml"


BRIDGE = ROOT / ".github" / "workflows" / "reserved-one-shot-trigger.yml"


def test_reserved_bridge_can_dispatch_verified_rereview():
    text = BRIDGE.read_text(encoding="utf-8")
    assert "verified_rereview" in text
    assert "gh workflow run issue698-scheduled-rereview.yml" in text


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_stage4_has_no_fixed_schedule_trigger():
    text = _text()
    assert "schedule:" not in text
    assert "cron:" not in text


def test_stage4_has_exactly_two_single_review_batches():
    text = _text()
    command = "member_verified_rereview_apply.py --queue-limit 5 --stale-days 30 --max-reviews 1 --request-budget 4"
    assert text.count(command) == 2
    assert "--max-reviews 2" not in text
    assert "--request-budget 5" not in text


def test_stage4_never_declares_lite_models():
    lowered = _text().lower()
    assert "flash_lite" not in lowered
    assert "flash-lite" not in lowered


def test_stage4_shares_global_gemini_concurrency_lock():
    text = _text()
    assert "group: ai-intelligence-gemini-budget" in text
    assert "cancel-in-progress: false" in text


def test_stage4_keeps_manual_kill_switch_path():
    text = _text()
    assert "workflow_dispatch:" in text
