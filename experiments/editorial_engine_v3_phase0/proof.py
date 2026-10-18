from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

from . import live
from .contract import validate_article_layout
from .runner import build_blind_package

BASELINE_AB_DIGESTS_NAME = "baseline_ab_digests.json"
PROOF_VERDICT_NAME = "proof_verdict.json"
PROOF_SCHEMA_VERSION = 1


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _canonical_case_ids() -> list[str]:
    return [item.case.case_id for item in live.READY_CASES]


def _canonical_input_digests() -> dict[str, str]:
    return {item.case.case_id: live._input_digest(item) for item in live.READY_CASES}


def _case_map(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = state.get("cases", [])
    if not isinstance(cases, list):
        return {}
    mapped: dict[str, dict[str, Any]] = {}
    for raw_case in cases:
        if not isinstance(raw_case, dict):
            continue
        case_id = str(raw_case.get("case_id") or "")
        if not case_id or case_id in mapped:
            return {}
        mapped[case_id] = raw_case
    return mapped


def snapshot_ab_baseline(output_dir: str | Path) -> dict[str, Any]:
    out_dir = Path(output_dir)
    state = live._load_checkpoint(out_dir)
    if not state:
        raise RuntimeError("Phase 0 baseline checkpoint is required before C-only proof")
    live._validate_checkpoint(state)

    canonical_ids = _canonical_case_ids()
    cases = _case_map(state)
    if list(cases) != canonical_ids:
        raise RuntimeError("Phase 0 baseline must contain the exact three canonical cases in order")

    case_digests: dict[str, dict[str, str]] = {}
    for case_id in canonical_ids:
        outputs = dict(cases[case_id].get("outputs") or {})
        a = str(outputs.get("A_CURRENT_WRITER") or "")
        b = str(outputs.get("B_PERSONA_ONLY") or "")
        if not a.strip() or not b.strip():
            raise RuntimeError(f"Phase 0 baseline is missing A/B outputs for {case_id}")
        case_digests[case_id] = {
            "A_CURRENT_WRITER": _sha256_text(a),
            "B_PERSONA_ONLY": _sha256_text(b),
        }

    payload = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "case_ids": canonical_ids,
        "case_digests": case_digests,
    }
    _atomic_write_json(out_dir / BASELINE_AB_DIGESTS_NAME, payload)
    return payload


def _artifact_case_ids(packages: Any) -> list[str]:
    if not isinstance(packages, list):
        return []
    result: list[str] = []
    for package in packages:
        if not isinstance(package, dict):
            return []
        case_id = str(package.get("case_id") or "")
        if not case_id:
            return []
        result.append(case_id)
    return result


def _expected_blind_artifacts(cases: dict[str, dict[str, Any]], canonical_ids: list[str]) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]] | None:
    packages: list[dict[str, Any]] = []
    mapping: dict[str, dict[str, str]] = {}
    try:
        for case_id in canonical_ids:
            outputs = dict(cases[case_id].get("outputs") or {})
            blind, case_mapping = build_blind_package(case_id, outputs)
            packages.append(blind)
            mapping[case_id] = case_mapping
    except (KeyError, ValueError):
        return None
    return packages, mapping


def _model_allowed(selected_model: str, model_candidates: Iterable[str] | None) -> bool:
    if not selected_model or "lite" in selected_model.lower():
        return False
    if model_candidates is None:
        return True
    candidates = tuple(str(model).strip() for model in model_candidates if str(model).strip())
    return bool(candidates) and selected_model in candidates and all("lite" not in model.lower() for model in candidates)


def evaluate_c_only_proof(
    output_dir: str | Path,
    *,
    model_candidates: Iterable[str] | None = None,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    state = live._load_checkpoint(out_dir) or {}
    baseline = _read_json(out_dir / BASELINE_AB_DIGESTS_NAME, {})
    disk_packages = _read_json(out_dir / "blind_packages.json", [])
    disk_mapping = _read_json(out_dir / "blind_mapping.json", {})
    raw_results = _read_json(out_dir / "raw_results.json", {})

    canonical_ids = _canonical_case_ids()
    canonical_digests = _canonical_input_digests()
    cases = _case_map(state)
    case_ids = list(cases)
    selected_model = str(state.get("selected_model") or "").strip()
    completed_ids = [str(case_id) for case_id in state.get("c_completed_case_ids", []) if str(case_id)]

    exact_case_set = case_ids == canonical_ids
    immutable_inputs = exact_case_set and all(
        str(cases[case_id].get("input_digest") or "") == canonical_digests[case_id]
        for case_id in canonical_ids
    )

    baseline_case_digests = baseline.get("case_digests", {}) if isinstance(baseline, dict) else {}
    baseline_ids = baseline.get("case_ids", []) if isinstance(baseline, dict) else []
    ab_byte_identical = baseline_ids == canonical_ids and exact_case_set
    if ab_byte_identical:
        for case_id in canonical_ids:
            expected = baseline_case_digests.get(case_id, {}) if isinstance(baseline_case_digests, dict) else {}
            outputs = dict(cases[case_id].get("outputs") or {})
            for variant in ("A_CURRENT_WRITER", "B_PERSONA_ONLY"):
                current = str(outputs.get(variant) or "")
                if not current or expected.get(variant) != _sha256_text(current):
                    ab_byte_identical = False
                    break
            if not ab_byte_identical:
                break

    completed_all_cases = completed_ids == canonical_ids
    five_stages_complete = exact_case_set
    final_matches_fact_safe_review = exact_case_set
    c_articles_layout_valid = exact_case_set
    if exact_case_set:
        for case_id in canonical_ids:
            case = cases[case_id]
            stages = dict(case.get("editorial_stage_outputs") or {})
            outputs = dict(case.get("outputs") or {})
            if set(stages) != set(live.EDITORIAL_STAGES) or any(
                not str(stages.get(stage) or "").strip() for stage in live.EDITORIAL_STAGES
            ):
                five_stages_complete = False
            final = str(outputs.get("C_EDITORIAL_ENGINE") or "").strip()
            reviewed = str(stages.get("Fact-Safe Review") or "").strip()
            if not final or final != reviewed:
                final_matches_fact_safe_review = False
            for article in (str(stages.get("Persona Article Generation") or ""), reviewed):
                try:
                    validate_article_layout(article)
                except ValueError:
                    c_articles_layout_valid = False

    state_package_ids = _artifact_case_ids(state.get("blind_packages", []))
    disk_package_ids = _artifact_case_ids(disk_packages)
    state_mapping = state.get("blind_mapping", {})
    blind_case_set_exact = state_package_ids == canonical_ids and disk_package_ids == canonical_ids

    expected_blind = _expected_blind_artifacts(cases, canonical_ids) if exact_case_set else None
    expected_packages, expected_mapping = expected_blind if expected_blind is not None else ([], {})
    blind_mapping_set_exact = (
        isinstance(state_mapping, dict)
        and isinstance(disk_mapping, dict)
        and state_mapping == expected_mapping
        and disk_mapping == expected_mapping
    )
    blind_articles_current = (
        isinstance(state.get("blind_packages", []), list)
        and isinstance(disk_packages, list)
        and state.get("blind_packages", []) == expected_packages
        and disk_packages == expected_packages
    )

    raw_case_ids = _artifact_case_ids(raw_results.get("cases", []) if isinstance(raw_results, dict) else [])
    raw_results_consistent = (
        isinstance(raw_results, dict)
        and raw_case_ids == canonical_ids
        and str(raw_results.get("model") or "").strip() == selected_model
        and str(raw_results.get("mode") or "") == "C_ONLY_REFINEMENT"
        and [str(case_id) for case_id in raw_results.get("c_completed_case_ids", [])] == canonical_ids
        and int(raw_results.get("c_refinement_provider_calls_total", -1) or -1) == live.C_ONLY_MAX_PROVIDER_CALLS
    )
    raw_results_current = (
        raw_results_consistent
        and raw_results.get("cases") == state.get("cases")
        and str(raw_results.get("c_refinement_fingerprint") or "")
        == str(state.get("c_refinement_fingerprint") or "")
    )

    checks = {
        "mode_c_only": state.get("mode") == "C_ONLY_REFINEMENT",
        "selected_model_allowed": _model_allowed(selected_model, model_candidates),
        "exact_case_set": exact_case_set,
        "immutable_inputs": immutable_inputs,
        "ab_byte_identical": ab_byte_identical,
        "current_fingerprint": str(state.get("c_refinement_fingerprint") or "") == live._c_refinement_fingerprint(),
        "completed_all_cases": completed_all_cases,
        "cumulative_provider_calls_exact": int(state.get("c_refinement_provider_calls_total", -1) or -1)
        == live.C_ONLY_MAX_PROVIDER_CALLS,
        "five_stages_complete": five_stages_complete,
        "final_matches_fact_safe_review": final_matches_fact_safe_review,
        "c_articles_layout_valid": c_articles_layout_valid,
        "blind_case_set_exact": blind_case_set_exact,
        "blind_mapping_set_exact": blind_mapping_set_exact,
        "blind_articles_current": blind_articles_current,
        "raw_results_consistent": raw_results_consistent,
        "raw_results_current": raw_results_current,
    }

    report = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "selected_model": selected_model or None,
        "cumulative_provider_calls": int(state.get("c_refinement_provider_calls_total", 0) or 0),
        "completed_case_ids": completed_ids,
        "checks": checks,
    }
    _atomic_write_json(out_dir / PROOF_VERDICT_NAME, report)
    return report


def _env_model_candidates() -> tuple[str, ...]:
    raw = str(os.environ.get("AIIF_PHASE0_MODELS") or "").strip()
    if not raw:
        return live.DEFAULT_MODEL_CANDIDATES
    candidates = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not candidates:
        raise RuntimeError("AIIF_PHASE0_MODELS must contain at least one model")
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Editorial Engine v3 Phase 0 structural proof verifier")
    parser.add_argument("action", choices=("snapshot-baseline", "verify"))
    parser.add_argument("--output-dir", default=os.environ.get("AIIF_PHASE0_OUTPUT_DIR", "phase0_artifacts"))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    if args.action == "snapshot-baseline":
        payload = snapshot_ab_baseline(output_dir)
        print(json.dumps({"status": "SNAPSHOT_OK", "case_ids": payload["case_ids"]}, ensure_ascii=False))
        return 0

    report = evaluate_c_only_proof(output_dir, model_candidates=_env_model_candidates())
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
