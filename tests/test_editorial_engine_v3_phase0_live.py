from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from experiments.editorial_engine_v3_phase0.contract import EDITORIAL_STAGES


def _article(body: str) -> str:
    return f"# 記事タイトル\n\n{body}"


def _reaction_first_payload(*, final: str = "# 記事タイトル\n\nreviewed final article") -> dict[str, str]:
    return {
        "Writer Reaction": "Reaction: curious\nCuriosity: why\nQuestion: really?\nFuture Imagination: what changes\nEmotion Intensity: MEDIUM",
        "Editorial Discovery": "Surface: update\nInteresting Tension: tension\nEvidence Pivot: evidence\nDeeper Insight: deeper\nEditorial Thesis: thesis",
        "Cognitive Shift": "Before View: before\nEvidence Encounter: evidence\nAfter View: after\nWhat I Now Find Interesting: discovery",
        "Persona Article Generation": _article("draft with writer-owned reaction and cognitive movement"),
        "Fact-Safe Review": final,
    }


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
    assert live.C_ONLY_MAX_PROVIDER_CALLS == 3


def test_editorial_bundle_requires_all_five_stages_and_uses_fact_safe_review_as_final() -> None:
    from experiments.editorial_engine_v3_phase0 import live

    final, stages = live._parse_editorial_bundle(json.dumps(_reaction_first_payload(), ensure_ascii=False))
    assert tuple(stages) == EDITORIAL_STAGES
    assert final == _article("reviewed final article")
    assert stages["Writer Reaction"]
    assert stages["Cognitive Shift"]
    assert stages["Persona Article Generation"]


@pytest.mark.parametrize("stage", ("Persona Article Generation", "Fact-Safe Review"))
def test_article_layout_rejects_literal_escape_only_in_prose(stage: str) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    payload = _reaction_first_payload()
    payload[stage] = "# 題名\\n\\nこれは文字としての改行です。"
    with pytest.raises(RuntimeError, match="invalid editorial bundle"):
        live._parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))

    payload[stage] = "# 題名\n\nこれは実際の改行です。"
    live._parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))

    payload[stage] = "# 題名\n\nコード `\\n` の説明です。"
    live._parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))

    payload[stage] = '# 題名\n\n段落です。\n\n```python\nprint("\\n")\n```'
    live._parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize("stage", ("Persona Article Generation", "Fact-Safe Review"))
@pytest.mark.parametrize("article", ("本文のみ", "# \n\n本文です。", "# 題名"))
def test_article_layout_rejects_missing_heading_or_body(stage: str, article: str) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    payload = _reaction_first_payload()
    payload[stage] = article
    with pytest.raises(RuntimeError, match="invalid editorial bundle"):
        live._parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))

    payload[stage] = "# 題名\n\n本文です。"
    live._parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize("missing_stage", EDITORIAL_STAGES)
def test_editorial_bundle_fails_closed_when_a_stage_is_missing(missing_stage: str) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    payload = _reaction_first_payload()
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


def test_c_only_refinement_reuses_a_b_records_five_stages_and_spends_three_calls(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    calls: list[str] = []

    class Models:
        def generate_content(self, *, model: str, contents: str):
            calls.append(model)
            payload = _reaction_first_payload(final=_article(f"reviewed-{len(calls)}"))
            return type("Response", (), {"text": json.dumps(payload, ensure_ascii=False)})()

    cases = []
    for item in live.READY_CASES:
        cases.append(
            {
                "case_id": item.case.case_id,
                "theme": item.theme,
                "input_digest": live._input_digest(item),
                "outputs": {
                    "A_CURRENT_WRITER": f"A-{item.case.case_id}",
                    "B_PERSONA_ONLY": f"B-{item.case.case_id}",
                    "C_EDITORIAL_ENGINE": f"old-C-{item.case.case_id}",
                },
                "editorial_stage_outputs": {},
            }
        )
    state = {
        "selected_model": "m1",
        "provider_calls": 6,
        "provider_attempts": 7,
        "cases": cases,
        "blind_packages": [],
        "blind_mapping": {},
    }
    client = type("Client", (), {"models": Models()})()
    session = live.ModelSession(candidates=("m1",), locked_model="m1")

    refined = live._run_c_only_refinement(
        client,
        session=session,
        state=state,
        output_dir=tmp_path,
        cooldown=0,
        sleep_fn=lambda _: None,
    )

    assert len(calls) == 3
    assert refined["provider_calls"] == 3
    assert refined["provider_attempts"] == 3
    assert refined["mode"] == "C_ONLY_REFINEMENT"
    assert refined["c_refinement_provider_calls_total"] == 3
    assert set(refined["c_completed_case_ids"]) == {item.case.case_id for item in live.READY_CASES}
    for index, case in enumerate(refined["cases"], start=1):
        assert case["outputs"]["A_CURRENT_WRITER"].startswith("A-")
        assert case["outputs"]["B_PERSONA_ONLY"].startswith("B-")
        assert case["outputs"]["C_EDITORIAL_ENGINE"] == _article(f"reviewed-{index}")
        assert tuple(case["editorial_stage_outputs"]) == EDITORIAL_STAGES


def test_c_only_refinement_resumes_same_fingerprint_and_calls_only_missing_case(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    calls: list[str] = []

    class Models:
        def generate_content(self, *, model: str, contents: str):
            calls.append(model)
            payload = _reaction_first_payload(final=_article("new-third"))
            return type("Response", (), {"text": json.dumps(payload, ensure_ascii=False)})()

    fingerprint = live._c_refinement_fingerprint()
    completed_ids = [item.case.case_id for item in live.READY_CASES[:2]]
    cases = []
    for index, item in enumerate(live.READY_CASES):
        stages = _reaction_first_payload(final=_article(f"kept-{index + 1}")) if index < 2 else {}
        cases.append(
            {
                "case_id": item.case.case_id,
                "theme": item.theme,
                "input_digest": live._input_digest(item),
                "outputs": {
                    "A_CURRENT_WRITER": f"A-{item.case.case_id}",
                    "B_PERSONA_ONLY": f"B-{item.case.case_id}",
                    "C_EDITORIAL_ENGINE": _article(f"kept-{index + 1}") if index < 2 else f"stale-{index + 1}",
                },
                "editorial_stage_outputs": stages,
            }
        )
    state = {
        "selected_model": "m1",
        "provider_calls": 2,
        "provider_attempts": 2,
        "baseline_provider_calls": 6,
        "baseline_provider_attempts": 7,
        "c_refinement_fingerprint": fingerprint,
        "c_completed_case_ids": completed_ids,
        "c_refinement_provider_calls_total": 2,
        "c_refinement_provider_attempts_total": 2,
        "cases": cases,
        "blind_packages": [],
        "blind_mapping": {},
    }
    client = type("Client", (), {"models": Models()})()
    session = live.ModelSession(candidates=("m1",), locked_model="m1")

    refined = live._run_c_only_refinement(
        client,
        session=session,
        state=state,
        output_dir=tmp_path,
        cooldown=0,
        sleep_fn=lambda _: None,
    )

    assert calls == ["m1"]
    assert refined["provider_calls"] == 1
    assert refined["c_refinement_provider_calls_total"] == 3
    assert set(refined["c_completed_case_ids"]) == {item.case.case_id for item in live.READY_CASES}
    assert refined["cases"][0]["outputs"]["C_EDITORIAL_ENGINE"] == _article("kept-1")
    assert refined["cases"][1]["outputs"]["C_EDITORIAL_ENGINE"] == _article("kept-2")
    assert refined["cases"][2]["outputs"]["C_EDITORIAL_ENGINE"] == _article("new-third")


def test_invalid_completed_c_resume_is_fail_closed_without_provider_call(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    calls: list[str] = []

    class Models:
        def generate_content(self, *, model: str, contents: str):
            calls.append(model)
            return type("Response", (), {"text": "should not generate"})()

    bad_article = "# 題名\\n\\nこれは改行のつもりです。"
    completed_id = live.READY_CASES[0].case.case_id
    cases = []
    for index, item in enumerate(live.READY_CASES):
        outputs = {
            "A_CURRENT_WRITER": f"A-{item.case.case_id}",
            "B_PERSONA_ONLY": f"B-{item.case.case_id}",
        }
        stages = {}
        if index == 0:
            outputs["C_EDITORIAL_ENGINE"] = bad_article
            stages = _reaction_first_payload(final=bad_article)
        cases.append({
            "case_id": item.case.case_id,
            "theme": item.theme,
            "input_digest": live._input_digest(item),
            "outputs": outputs,
            "editorial_stage_outputs": stages,
        })

    blind, mapping = live.build_blind_package(completed_id, cases[0]["outputs"])
    state = {
        "mode": "C_ONLY_REFINEMENT",
        "selected_model": "m1",
        "cases": cases,
        "c_refinement_fingerprint": live._c_refinement_fingerprint(),
        "c_completed_case_ids": [completed_id],
        "c_refinement_provider_calls_total": 1,
        "c_refinement_provider_attempts_total": 1,
        "blind_packages": [blind],
        "blind_mapping": {completed_id: mapping},
    }
    live._write_checkpoint(tmp_path, state)
    live._write_evaluation_artifacts(tmp_path, state)

    with pytest.raises(RuntimeError, match="invalid.*C-only.*checkpoint"):
        live._run_c_only_refinement(
            type("Client", (), {"models": Models()})(),
            session=live.ModelSession(candidates=("m1",), locked_model="m1"),
            state=state,
            output_dir=tmp_path,
            cooldown=0,
            sleep_fn=lambda _: None,
        )

    assert calls == []
    checkpoint = live._load_checkpoint(tmp_path)
    assert checkpoint is not None
    assert checkpoint["c_refinement_provider_calls_total"] == 1
    assert checkpoint["blind_packages"] == []
    assert json.loads((tmp_path / "blind_packages.json").read_text(encoding="utf-8")) == []
    assert bad_article not in (tmp_path / "blind_evaluation.md").read_text(encoding="utf-8")
    assert [(case["outputs"]["A_CURRENT_WRITER"], case["outputs"]["B_PERSONA_ONLY"])
            for case in checkpoint["cases"]] == [
        (f"A-{item.case.case_id}", f"B-{item.case.case_id}") for item in live.READY_CASES
    ]


def test_c_only_refinement_fingerprint_change_regenerates_all_c_cases(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    calls: list[str] = []

    class Models:
        def generate_content(self, *, model: str, contents: str):
            calls.append(model)
            payload = _reaction_first_payload(final=_article(f"fresh-{len(calls)}"))
            return type("Response", (), {"text": json.dumps(payload, ensure_ascii=False)})()

    cases = []
    for index, item in enumerate(live.READY_CASES):
        cases.append(
            {
                "case_id": item.case.case_id,
                "theme": item.theme,
                "input_digest": live._input_digest(item),
                "outputs": {
                    "A_CURRENT_WRITER": f"A-{item.case.case_id}",
                    "B_PERSONA_ONLY": f"B-{item.case.case_id}",
                    "C_EDITORIAL_ENGINE": f"old-{index + 1}",
                },
                "editorial_stage_outputs": _reaction_first_payload(final=_article(f"old-{index + 1}")),
            }
        )
    state = {
        "selected_model": "m1",
        "provider_calls": 2,
        "provider_attempts": 2,
        "baseline_provider_calls": 6,
        "baseline_provider_attempts": 7,
        "c_refinement_fingerprint": "stale-fingerprint",
        "c_completed_case_ids": [item.case.case_id for item in live.READY_CASES[:2]],
        "c_refinement_provider_calls_total": 2,
        "c_refinement_provider_attempts_total": 2,
        "cases": cases,
        "blind_packages": [],
        "blind_mapping": {},
    }
    client = type("Client", (), {"models": Models()})()
    session = live.ModelSession(candidates=("m1",), locked_model="m1")

    refined = live._run_c_only_refinement(
        client,
        session=session,
        state=state,
        output_dir=tmp_path,
        cooldown=0,
        sleep_fn=lambda _: None,
    )

    assert calls == ["m1", "m1", "m1"]
    assert refined["provider_calls"] == 3
    assert refined["c_refinement_provider_calls_total"] == 3
    assert refined["c_refinement_fingerprint"] == live._c_refinement_fingerprint()
    assert [case["outputs"]["C_EDITORIAL_ENGINE"] for case in refined["cases"]] == [
        _article("fresh-1"),
        _article("fresh-2"),
        _article("fresh-3"),
    ]


def test_new_fingerprint_scrubs_stale_c_before_first_failed_provider_call(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live

    class Models:
        def generate_content(self, *, model: str, contents: str):
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    cases = []
    stale_packages = []
    stale_mapping: dict[str, dict[str, str]] = {}
    for index, item in enumerate(live.READY_CASES):
        outputs = {
            "A_CURRENT_WRITER": f"A-{item.case.case_id}",
            "B_PERSONA_ONLY": f"B-{item.case.case_id}",
            "C_EDITORIAL_ENGINE": f"stale-{index + 1}",
        }
        blind, mapping = live.build_blind_package(item.case.case_id, outputs)
        stale_packages.append(blind)
        stale_mapping[item.case.case_id] = mapping
        cases.append(
            {
                "case_id": item.case.case_id,
                "theme": item.theme,
                "input_digest": live._input_digest(item),
                "outputs": outputs,
                "editorial_stage_outputs": _reaction_first_payload(final=_article(f"stale-{index + 1}")),
            }
        )

    state = {
        "selected_model": "m1",
        "provider_calls": 2,
        "provider_attempts": 2,
        "baseline_provider_calls": 6,
        "baseline_provider_attempts": 7,
        "c_refinement_fingerprint": "old-prompt-fingerprint",
        "c_completed_case_ids": [item.case.case_id for item in live.READY_CASES[:2]],
        "c_refinement_provider_calls_total": 2,
        "c_refinement_provider_attempts_total": 2,
        "cases": cases,
        "blind_packages": stale_packages,
        "blind_mapping": stale_mapping,
    }
    (tmp_path / "blind_packages.json").write_text(json.dumps(stale_packages), encoding="utf-8")
    (tmp_path / "raw_results.json").write_text(json.dumps({"cases": cases}), encoding="utf-8")

    client = type("Client", (), {"models": Models()})()
    session = live.ModelSession(candidates=("m1",), locked_model="m1")

    with pytest.raises(RuntimeError, match="429"):
        live._run_c_only_refinement(
            client,
            session=session,
            state=state,
            output_dir=tmp_path,
            cooldown=0,
            sleep_fn=lambda _: None,
        )

    checkpoint = live._load_checkpoint(tmp_path)
    assert checkpoint is not None
    assert checkpoint["c_completed_case_ids"] == []
    assert checkpoint["blind_packages"] == []
    assert checkpoint["blind_mapping"] == {}
    for case in checkpoint["cases"]:
        assert set(case["outputs"]) == {"A_CURRENT_WRITER", "B_PERSONA_ONLY"}
        assert case["editorial_stage_outputs"] == {}

    assert json.loads((tmp_path / "blind_packages.json").read_text(encoding="utf-8")) == []
    raw = json.loads((tmp_path / "raw_results.json").read_text(encoding="utf-8"))
    for case in raw["cases"]:
        assert set(case["outputs"]) == {"A_CURRENT_WRITER", "B_PERSONA_ONLY"}
        assert case["editorial_stage_outputs"] == {}
