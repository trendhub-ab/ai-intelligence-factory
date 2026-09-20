from pathlib import Path


def test_stale_ready_mode_is_distinct_workflow_choice():
    text=Path(".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    assert "- ready_rescue_validation\\n          - stale_ready_batch_revalidation" not in text
    assert "\n          - ready_rescue_validation\n          - stale_ready_batch_revalidation\n" in text
