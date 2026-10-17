from __future__ import annotations

import importlib.util
import json

import pytest

from experiments.editorial_engine_v3_phase0.contract import EDITORIAL_STAGES


def test_live_module_exists_and_uses_fixed_non_lite_model() -> None:
    spec = importlib.util.find_spec("experiments.editorial_engine_v3_phase0.live")
    assert spec is not None
    from experiments.editorial_engine_v3_phase0 import live

    assert live.DEFAULT_MODEL == "gemini-3.6-flash"
    assert "lite" not in live.DEFAULT_MODEL.lower()


def test_live_experiment_has_exact_expected_call_budget() -> None:
    from experiments.editorial_engine_v3_phase0 import live

    assert live.B_CALLS_PER_CASE == 1
    assert live.C_CALLS_PER_CASE == 1
    assert live.EXPECTED_CASES == 3
    assert live.MAX_PROVIDER_CALLS == 6


def test_editorial_bundle_requires_all_four_stages_and_uses_review_as_final() -> None:
    from experiments.editorial_engine_v3_phase0 import live

    payload = json.dumps(
        {
            "Editorial Discovery": "discovery",
            "Persona Narrative": "narrative",
            "Article Writing": "draft",
            "Editorial Review": "reviewed final article",
        },
        ensure_ascii=False,
    )
    final, stages = live._parse_editorial_bundle(payload)
    assert tuple(stages) == EDITORIAL_STAGES
    assert final == "reviewed final article"


@pytest.mark.parametrize("missing_stage", EDITORIAL_STAGES)
def test_editorial_bundle_fails_closed_when_a_stage_is_missing(missing_stage: str) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    payload = {
        "Editorial Discovery": "discovery",
        "Persona Narrative": "narrative",
        "Article Writing": "draft",
        "Editorial Review": "reviewed final article",
    }
    payload.pop(missing_stage)
    with pytest.raises(RuntimeError, match="editorial bundle"):
        live._parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))
