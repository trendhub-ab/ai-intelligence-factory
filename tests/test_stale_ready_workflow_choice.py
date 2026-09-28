from pathlib import Path


def test_stale_ready_mode_is_distinct_workflow_choice():
    text=Path(".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    # Literal backslash-n must never join the two GitHub choice values.
    assert "ready_rescue_validation\\\\n          - stale_ready_batch_revalidation" not in text
    lines=[line.strip() for line in text.splitlines()]
    assert "- ready_rescue_validation" in lines
    assert "- stale_ready_batch_revalidation" in lines


def test_exact_target_is_allowed_only_for_article_or_stale_ready_revalidation():
    daily=Path(".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    reserved=Path(".github/workflows/reserved-one-shot-trigger.yml").read_text(encoding="utf-8")
    for text in (daily,reserved):
        assert "stale_ready_batch_revalidation" in text
        assert "exact_target is article_validation/stale_ready_batch_revalidation-only" in text
    assert 'inputs.mode != \'stale_ready_batch_revalidation\'' in daily
    assert '$mode" != "stale_ready_batch_revalidation"' in reserved
