from __future__ import annotations

import json
from pathlib import Path


def _baseline_state(live) -> dict:
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
    return {
        "selected_model": "gemini-3.8-flash",
        "mode": "FULL",
        "provider_calls": 6,
        "provider_attempts": 6,
        "cases": cases,
        "blind_packages": [],
        "blind_mapping": {},
    }


def _complete_current_refinement(live, state: dict) -> None:
    state["mode"] = "C_ONLY_REFINEMENT"
    state["c_refinement_fingerprint"] = live._c_refinement_fingerprint()
    state["c_completed_case_ids"] = [item.case.case_id for item in live.READY_CASES]
    state["c_refinement_provider_calls_total"] = 3
    state["c_refinement_provider_attempts_total"] = 3
    state["provider_calls"] = 3
    state["provider_attempts"] = 3
    for index, case in enumerate(state["cases"], start=1):
        final = f"reviewed-{index}"
        case["outputs"]["C_EDITORIAL_ENGINE"] = final
        case["editorial_stage_outputs"] = {
            "Writer Reaction": f"reaction-{index}",
            "Editorial Discovery": f"discovery-{index}",
            "Cognitive Shift": f"shift-{index}",
            "Persona Article Generation": f"draft-{index}",
            "Fact-Safe Review": final,
        }
    live._rebuild_blind_state(state)


def test_c_only_structural_proof_verdict_passes_for_complete_current_fingerprint(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live, proof

    state = _baseline_state(live)
    live._write_checkpoint(tmp_path, state)
    proof.snapshot_ab_baseline(tmp_path)

    _complete_current_refinement(live, state)
    live._write_checkpoint(tmp_path, state)
    live._write_evaluation_artifacts(tmp_path, state)

    report = proof.evaluate_c_only_proof(tmp_path, model_candidates=("gemini-3.8-flash",))

    assert report["status"] == "PASS"
    assert all(report["checks"].values())
    assert report["selected_model"] == "gemini-3.8-flash"
    assert report["cumulative_provider_calls"] == 3
    persisted = json.loads((tmp_path / proof.PROOF_VERDICT_NAME).read_text(encoding="utf-8"))
    assert persisted["status"] == "PASS"


def test_c_only_structural_proof_verdict_fails_when_a_or_b_changes(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live, proof

    state = _baseline_state(live)
    live._write_checkpoint(tmp_path, state)
    proof.snapshot_ab_baseline(tmp_path)

    _complete_current_refinement(live, state)
    state["cases"][0]["outputs"]["A_CURRENT_WRITER"] += " tampered"
    live._write_checkpoint(tmp_path, state)
    live._write_evaluation_artifacts(tmp_path, state)

    report = proof.evaluate_c_only_proof(tmp_path, model_candidates=("gemini-3.8-flash",))

    assert report["status"] == "FAIL"
    assert report["checks"]["ab_byte_identical"] is False


def test_c_only_structural_proof_verdict_fails_when_cumulative_calls_are_not_exactly_three(tmp_path: Path) -> None:
    from experiments.editorial_engine_v3_phase0 import live, proof

    state = _baseline_state(live)
    live._write_checkpoint(tmp_path, state)
    proof.snapshot_ab_baseline(tmp_path)

    _complete_current_refinement(live, state)
    state["c_refinement_provider_calls_total"] = 2
    live._write_checkpoint(tmp_path, state)
    live._write_evaluation_artifacts(tmp_path, state)

    report = proof.evaluate_c_only_proof(tmp_path, model_candidates=("gemini-3.8-flash",))

    assert report["status"] == "FAIL"
    assert report["checks"]["cumulative_provider_calls_exact"] is False
