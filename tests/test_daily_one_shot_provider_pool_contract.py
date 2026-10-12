from pathlib import Path

import run260_gemini_model_routing as routing


WORKFLOW = Path(".github/workflows/daily-one-shot.yml")


def test_daily_one_shot_exposes_canonical_variable_article_pool():
    text = WORKFLOW.read_text(encoding="utf-8")
    expected = ",".join(routing.DEFAULT_DEEP_DIVE_POOL)
    assert f'GEMINI_DEEP_DIVE_MODEL_CANDIDATES: "{expected}"' in text


def test_daily_one_shot_operator_exclusion_accepts_preview_model():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'gemini-3-flash-preview)' in text
