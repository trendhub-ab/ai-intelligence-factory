from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from experiments.editorial_engine_v3_phase0.contract import EDITORIAL_STAGES


def test_live_module_exists_and_uses_variable_non_lite_model_candidates() -> None:
    spec = importlib.util.find_spec("experiments.editorial_engine_v3_phase0.live")
    assert spec is not None
    from experiments.editorial_engine_v3_phase0 import live

    assert len(live.DEFAULT_MODEL_CANDIDATES) >= 2
    assert all("lite" not in model.lower() for model in live.DEFAULT_MODEL_CANDIDATES)
    assert live.DEFAULT_MODEL_CANDIDATES[0] == "gemini-3.8-flash"


def test_live_experiment_has_exact_expected_logical_call_budget() -> None:
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


def test_model_candidates_can_be_overridden_without_lite(monkeypatch: pytest.MonkeyPatch) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    monkeypatch.setenv("AIIF_PHASE0_MODELS", "gemini-3.6-flash, gemini-3.8-flash")
    assert live._model_candidates() == ("gemini-3.6-flash", "gemini-3.8-flash")

    monkeypatch.setenv("AIIF_PHASE0_MODELS", "gemini-3.8-flash,gemini-flash-lite")
    with pytest.raises(RuntimeError, match="non-Lite"):
        live._model_candidates()


def test_model_fallback_is_allowed_only_before_first_success() -> None:
    from experiments.editorial_engine_v3_phase0 import live

    calls: list[str] = []

    class Models:
        def generate_content(self, *, model: str, contents: str):
            calls.append(model)
            if model == "m1":
                raise RuntimeError("503 UNAVAILABLE high demand")
            return type("Response", (), {"text": "ok"})()

    client = type("Client", (), {"models": Models()})()
    session = live.ModelSession(candidates=("m1", "m2"))
    text = live._provider_text_resilient(client, session=session, prompt="p", sleep_fn=lambda _: None)

    assert text == "ok"
    assert session.locked_model == "m2"
    assert calls == ["m1", "m2"]


def test_locked_model_never_falls_back_after_success() -> None:
    from experiments.editorial_engine_v3_phase0 import live

    calls: list[str] = []

    class Models:
        def generate_content(self, *, model: str, contents: str):
            calls.append(model)
            if len(calls) == 1:
                return type("Response", (), {"text": "first success"})()
            raise RuntimeError("503 UNAVAILABLE high demand")

    client = type("Client", (), {"models": Models()})()
    session = live.ModelSession(candidates=("m1", "m2"))
    assert live._provider_text_resilient(client, session=session, prompt="first", sleep_fn=lambda _: None) == "first success"

    with pytest.raises(RuntimeError, match="503"):
        live._provider_text_resilient(client, session=session, prompt="second", sleep_fn=lambda _: None)

    assert session.locked_model == "m1"
    assert set(calls) == {"m1"}


def test_checkpoint_round_trip_and_completed_case_skip(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    payload = {
        "selected_model": "gemini-3.8-flash",
        "provider_calls": 2,
        "provider_attempts": 2,
        "cases": [{"case_id": "case-1", "input_digest": "abc"}],
        "blind_packages": [{"case_id": "case-1", "candidates": []}],
        "blind_mapping": {"case-1": {"X": "A_CURRENT_WRITER"}},
    }
    live._write_checkpoint(tmp_path, payload)
    restored = live._load_checkpoint(tmp_path)

    assert restored == payload
    assert live._completed_case_ids(restored) == {"case-1"}


def test_case_cooldown_is_configurable_and_non_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    monkeypatch.setenv("AIIF_PHASE0_CASE_COOLDOWN_SECONDS", "45")
    assert live._case_cooldown_seconds() == 45.0

    monkeypatch.setenv("AIIF_PHASE0_CASE_COOLDOWN_SECONDS", "-1")
    with pytest.raises(RuntimeError, match="cooldown"):
        live._case_cooldown_seconds()
