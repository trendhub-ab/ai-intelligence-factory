from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
PIPELINE = ROOT / "pipeline.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_daily_one_shot_routes_screening_to_lite_only_without_flash_fallbacks():
    workflow = _text(WORKFLOW)
    screening_line = next(
        line for line in workflow.splitlines() if "GEMINI_SCREENING_MODEL_CANDIDATES:" in line
    )
    assert screening_line.strip() == (
        'GEMINI_SCREENING_MODEL_CANDIDATES: "gemini-3.1-flash-lite"'
    )


def test_daily_one_shot_allows_run_scoped_exclusion_of_screening_lite():
    workflow = _text(WORKFLOW)
    assert (
        '""|gemini-3.1-flash-lite|gemini-3.5-flash|gemini-3.6-flash|gemini-3.7-flash|gemini-3.8-flash) ;;'
        in workflow
    )


def test_daily_one_shot_keeps_deep_dive_pool_lite_free():
    workflow = _text(WORKFLOW)
    assert (
        'GEMINI_DEEP_DIVE_MODEL_CANDIDATES: "gemini-3.6-flash,gemini-3.5-flash,gemini-3.7-flash,gemini-3.8-flash"'
        in workflow
    )
    deep_dive_line = next(
        line for line in workflow.splitlines() if "GEMINI_DEEP_DIVE_MODEL_CANDIDATES:" in line
    )
    assert "flash-lite" not in deep_dive_line.lower()


def test_public_article_writer_remains_fail_closed_against_flash_lite():
    pipeline = _text(PIPELINE)
    assert 'Public article Writer cannot use Flash-Lite' in pipeline
    assert 'if "flash-lite" in str(selected_model or "").lower()' in pipeline
