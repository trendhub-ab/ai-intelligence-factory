"""AIIF V2-005 offline evidence-pack validation and rendering.

This module never performs network/model/Production work. It validates 3-5
measured V2-005 shadow artifacts, aggregates only safe review fields, and keeps
promotion authority human-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from v2_shadow_observation import EVIDENCE_MODEL_POOL


PROOF_VERSION = "V2-005"
PROMOTION_DECISION = "human_review_required"
MIN_RUNS = 3
MAX_RUNS = 5
MAX_RATIONALE_CHARS = 1000

_ALLOWED_OUTCOMES = {
    "sufficient",
    "insufficient_evidence",
    "provider_failure",
    "not_attempted",
    "invalid_result",
}
_ALLOWED_VERDICTS = {
    "v2_better",
    "equivalent",
    "v1_better",
    "not_comparable",
}
_SAFE_PROVIDER_ERROR_CODES = {
    "provider_request_failed",
    "provider_http_400",
    "provider_http_401_403",
    "provider_http_404",
    "provider_http_429",
    "provider_http_5xx",
    "provider_timeout",
    "provider_connection_error",
    "provider_response_json_invalid",
    "provider_response_shape_invalid",
    "provider_evidence_contract_invalid",
}
_USAGE_KEYS = (
    "prompt_token_count",
    "candidate_token_count",
    "total_token_count",
)
_SAFE_CANDIDATE_FIELDS = (
    "candidate_identity",
    "provider",
    "title",
    "source_timestamp",
    "screening_score",
    "screening_reasons",
)


class EvidencePackContractError(ValueError):
    """One or more V2-005 proof artifacts violated the review-pack contract."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidencePackContractError(f"{label}_not_mapping")
    return value


def _logical_request_count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in {0, 1}:
        raise EvidencePackContractError(f"{label}_invalid")
    return value


def _provider_request_count(value: Any, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > len(EVIDENCE_MODEL_POOL)
    ):
        raise EvidencePackContractError(f"{label}_invalid")
    return value


def _usage(value: Any) -> dict[str, int] | None:
    if value is None:
        return None
    raw = _mapping(value, "provider_usage")
    if set(raw) != set(_USAGE_KEYS):
        raise EvidencePackContractError("provider_usage_keys_invalid")
    normalized: dict[str, int] = {}
    for key in _USAGE_KEYS:
        item = raw.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise EvidencePackContractError("provider_usage_value_invalid")
        normalized[key] = item
    return normalized


def _candidate(value: Any, *, attempted: int) -> dict[str, Any] | None:
    if attempted == 0:
        if value is not None:
            raise EvidencePackContractError("unevaluated_candidate_present")
        return None
    raw = _mapping(value, "evaluated_candidate")
    if set(raw) != set(_SAFE_CANDIDATE_FIELDS):
        raise EvidencePackContractError("evaluated_candidate_keys_invalid")
    identity = raw.get("candidate_identity")
    provider = raw.get("provider")
    title = raw.get("title")
    score = raw.get("screening_score")
    reasons = raw.get("screening_reasons")
    if not isinstance(identity, str) or not identity.strip():
        raise EvidencePackContractError("candidate_identity_invalid")
    if not isinstance(provider, str) or not provider.strip():
        raise EvidencePackContractError("candidate_provider_invalid")
    if not isinstance(title, str) or not title.strip():
        raise EvidencePackContractError("candidate_title_invalid")
    if isinstance(score, bool) or not isinstance(score, int):
        raise EvidencePackContractError("candidate_screening_score_invalid")
    if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
        raise EvidencePackContractError("candidate_screening_reasons_invalid")
    timestamp = raw.get("source_timestamp")
    if timestamp is not None and not isinstance(timestamp, str):
        raise EvidencePackContractError("candidate_source_timestamp_invalid")
    return {
        "candidate_identity": identity.strip(),
        "provider": provider.strip(),
        "title": title.strip(),
        "source_timestamp": timestamp,
        "screening_score": score,
        "screening_reasons": list(reasons),
    }


def _validate_human_reviews(
    human_reviews: Mapping[str, Any] | None,
    *,
    run_ids: set[str],
) -> dict[str, dict[str, Any]]:
    if human_reviews is None:
        return {}
    raw_reviews = _mapping(human_reviews, "human_reviews")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_run_id, raw_review in raw_reviews.items():
        if not isinstance(raw_run_id, str) or raw_run_id not in run_ids:
            raise EvidencePackContractError("human_review_unknown_run_id")
        review = _mapping(raw_review, "human_review")
        if set(review) != {"v1_candidate_identity", "verdict", "rationale"}:
            raise EvidencePackContractError("human_review_keys_invalid")
        identity = review.get("v1_candidate_identity")
        if identity is not None:
            if not isinstance(identity, str):
                raise EvidencePackContractError("v1_candidate_identity_invalid")
            identity = identity.strip() or None
        verdict = review.get("verdict")
        if verdict not in _ALLOWED_VERDICTS:
            raise EvidencePackContractError("human_review_verdict_invalid")
        rationale = review.get("rationale")
        if not isinstance(rationale, str):
            raise EvidencePackContractError("human_review_rationale_invalid")
        rationale = " ".join(rationale.split()).strip()
        if not rationale or len(rationale) > MAX_RATIONALE_CHARS:
            raise EvidencePackContractError("human_review_rationale_invalid")
        normalized[raw_run_id] = {
            "v1_candidate_identity": identity,
            "verdict": verdict,
            "rationale": rationale,
        }
    return normalized


def _validate_report(report: Mapping[str, Any]) -> dict[str, Any]:
    run_id = report.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise EvidencePackContractError("run_id_invalid")
    run_id = run_id.strip()
    if report.get("mode") != "shadow":
        raise EvidencePackContractError("run_mode_invalid")

    observation = _mapping(report.get("observation"), "observation")
    if observation.get("mode") != "provider_backed_one_shot":
        raise EvidencePackContractError("observation_mode_invalid")
    if observation.get("production_authority") != "v1":
        raise EvidencePackContractError("production_authority_invalid")
    if observation.get("diagnostic_only") is not True:
        raise EvidencePackContractError("diagnostic_only_invalid")

    raw_pool = observation.get("evidence_model_pool")
    if (
        not isinstance(raw_pool, list)
        or len(raw_pool) != len(EVIDENCE_MODEL_POOL)
        or len(set(raw_pool)) != len(raw_pool)
        or set(raw_pool) != set(EVIDENCE_MODEL_POOL)
    ):
        raise EvidencePackContractError("evidence_model_pool_invalid")
    model = observation.get("model")
    if model not in raw_pool:
        raise EvidencePackContractError("model_invalid")
    selected_model = observation.get("selected_evidence_model")
    if selected_model is not None and selected_model not in raw_pool:
        raise EvidencePackContractError("selected_evidence_model_invalid")
    if observation.get("request_budget") != len(EVIDENCE_MODEL_POOL):
        raise EvidencePackContractError("request_budget_invalid")

    actual_calls = _mapping(report.get("actual_calls"), "actual_calls")
    actual_count = _logical_request_count(
        actual_calls.get("deep_dive"),
        "actual_deep_dive_count",
    )

    measurement = _mapping(report.get("v2_005_measurement"), "v2_005_measurement")
    if measurement.get("proof_version") != PROOF_VERSION:
        raise EvidencePackContractError("proof_version_invalid")
    measured_count = _provider_request_count(
        measurement.get("provider_request_count"),
        "provider_request_count",
    )
    if actual_count == 0 and measured_count != 0:
        raise EvidencePackContractError("provider_request_count_mismatch")
    if actual_count == 1 and measured_count == 0:
        raise EvidencePackContractError("provider_request_count_mismatch")
    if measurement.get("production_mutation_authorized") is not False:
        raise EvidencePackContractError("production_mutation_authorized")
    if measurement.get("promotion_decision") != PROMOTION_DECISION:
        raise EvidencePackContractError("promotion_decision_invalid")

    candidate = _candidate(
        measurement.get("evaluated_candidate"),
        attempted=actual_count,
    )
    usage = _usage(measurement.get("provider_usage"))

    outcome = report.get("deep_dive_result_category")
    if outcome not in _ALLOWED_OUTCOMES:
        raise EvidencePackContractError("deep_dive_result_category_invalid")
    selected = report.get("v2_selected_candidate_identity")
    if outcome == "sufficient":
        if not isinstance(selected, str) or not selected.strip():
            raise EvidencePackContractError("winner_missing")
        selected = selected.strip()
        result = _mapping(observation.get("provider_result"), "provider_result")
        if result.get("evidence_sufficient") is not True:
            raise EvidencePackContractError("sufficient_result_invalid")
        if selected_model is None or model != selected_model:
            raise EvidencePackContractError("selected_evidence_model_missing")
    else:
        if selected is not None:
            raise EvidencePackContractError("non_sufficient_winner_present")
        if outcome == "insufficient_evidence":
            result = _mapping(observation.get("provider_result"), "provider_result")
            if result.get("evidence_sufficient") is not False:
                raise EvidencePackContractError("insufficient_result_invalid")
            if selected_model is None or model != selected_model:
                raise EvidencePackContractError("selected_evidence_model_missing")
        elif outcome in {"provider_failure", "not_attempted"} and selected_model is not None:
            raise EvidencePackContractError("unexpected_selected_evidence_model")

    error_code = observation.get("provider_error_category")
    if outcome == "provider_failure":
        if error_code not in _SAFE_PROVIDER_ERROR_CODES:
            raise EvidencePackContractError("provider_error_category_invalid")
    elif error_code is not None:
        raise EvidencePackContractError("unexpected_provider_error_category")

    timestamp = report.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise EvidencePackContractError("timestamp_invalid")

    return {
        "run_id": run_id,
        "timestamp": timestamp.strip(),
        "outcome": outcome,
        "selected_candidate_identity": selected,
        "evaluated_candidate": candidate,
        "selected_evidence_model": selected_model,
        "provider_request_count": measured_count,
        "provider_usage": usage,
        "provider_error_category": error_code,
    }


def build_evidence_pack(
    reports: Sequence[Mapping[str, Any]],
    human_reviews: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and aggregate 3-5 V2-005 shadow proof artifacts."""

    if isinstance(reports, (str, bytes)) or not isinstance(reports, Sequence):
        raise EvidencePackContractError("reports_invalid")
    if not MIN_RUNS <= len(reports) <= MAX_RUNS:
        raise EvidencePackContractError("run_count_invalid")

    validated = [_validate_report(_mapping(report, "report")) for report in reports]
    run_ids = [row["run_id"] for row in validated]
    if len(set(run_ids)) != len(run_ids):
        raise EvidencePackContractError("duplicate_run_id")

    reviews = _validate_human_reviews(human_reviews, run_ids=set(run_ids))
    rows = []
    for row in sorted(validated, key=lambda item: item["run_id"]):
        review = reviews.get(row["run_id"])
        rows.append(
            {
                **row,
                "review_status": "reviewed" if review is not None else "not_reviewed",
                "human_review": review,
            }
        )

    winner_count = sum(row["outcome"] == "sufficient" for row in rows)
    sufficient_count = winner_count
    insufficient_count = sum(row["outcome"] == "insufficient_evidence" for row in rows)
    failure_count = sum(row["outcome"] == "provider_failure" for row in rows)
    not_attempted_count = sum(row["outcome"] == "not_attempted" for row in rows)
    invalid_result_count = sum(row["outcome"] == "invalid_result" for row in rows)
    request_total = sum(row["provider_request_count"] for row in rows)

    observed_usage = [row["provider_usage"] for row in rows if row["provider_usage"] is not None]
    usage_totals = None
    if observed_usage:
        usage_totals = {
            key: sum(usage[key] for usage in observed_usage)
            for key in _USAGE_KEYS
        }

    provider_error_counts: dict[str, int] = {}
    for row in rows:
        code = row["provider_error_category"]
        if code is not None:
            provider_error_counts[code] = provider_error_counts.get(code, 0) + 1

    return {
        "proof_version": PROOF_VERSION,
        "run_count": len(rows),
        "winner_count": winner_count,
        "evidence_sufficient_count": sufficient_count,
        "evidence_insufficient_count": insufficient_count,
        "provider_failure_count": failure_count,
        "not_attempted_count": not_attempted_count,
        "invalid_result_count": invalid_result_count,
        "provider_request_count_total": request_total,
        "provider_usage_observed_run_count": len(observed_usage),
        "provider_usage_totals": usage_totals,
        "provider_error_counts": dict(sorted(provider_error_counts.items())),
        "human_reviewed_run_count": len(reviews),
        "runs": rows,
        "promotion_decision": PROMOTION_DECISION,
    }


def render_evidence_pack_markdown(pack: Mapping[str, Any]) -> str:
    """Render a deterministic compact human-review summary."""

    if pack.get("proof_version") != PROOF_VERSION:
        raise EvidencePackContractError("pack_proof_version_invalid")
    lines = [
        "# V2-005 Live Proof Evidence Pack",
        "",
        f"- Runs: {pack.get('run_count')}",
        f"- Shadow winners: {pack.get('winner_count')}",
        f"- Evidence sufficient: {pack.get('evidence_sufficient_count')}",
        f"- Evidence insufficient: {pack.get('evidence_insufficient_count')}",
        f"- Provider failures: {pack.get('provider_failure_count')}",
        f"- Provider requests: {pack.get('provider_request_count_total')}",
        f"- Usage observed runs: {pack.get('provider_usage_observed_run_count')}",
        f"- Human-reviewed runs: {pack.get('human_reviewed_run_count')}",
        "",
        "## Runs",
        "",
        "| Run | Candidate | Outcome | Requests | Review |",
        "| --- | --- | --- | ---: | --- |",
    ]
    runs = pack.get("runs")
    if not isinstance(runs, list):
        raise EvidencePackContractError("pack_runs_invalid")
    for row in runs:
        item = _mapping(row, "pack_run")
        candidate = item.get("evaluated_candidate")
        title = "—"
        if isinstance(candidate, Mapping):
            raw_title = candidate.get("title")
            if isinstance(raw_title, str) and raw_title.strip():
                title = raw_title.strip().replace("|", "/")
        lines.append(
            "| "
            + " | ".join(
                (
                    str(item.get("run_id") or ""),
                    title,
                    str(item.get("outcome") or ""),
                    str(item.get("provider_request_count") or 0),
                    str(item.get("review_status") or ""),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Promotion decision: HUMAN REVIEW REQUIRED — "
            "this evidence pack cannot authorize V2-006 automatically.",
        ]
    )
    return "\n".join(lines)


def write_evidence_pack(
    pack: Mapping[str, Any],
    *,
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Write only the requested deterministic JSON and Markdown artifacts."""

    json_output = Path(json_path)
    markdown_output = Path(markdown_path)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(
            dict(pack),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_output.write_text(
        render_evidence_pack_markdown(pack) + "\n",
        encoding="utf-8",
    )
    return json_output, markdown_output


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build offline V2-005 evidence pack")
    parser.add_argument("reports", nargs="+")
    parser.add_argument("--human-review")
    parser.add_argument(
        "--json-output",
        default="article_audit/v2_005_evidence_pack.json",
    )
    parser.add_argument(
        "--markdown-output",
        default="article_audit/v2_005_evidence_pack.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    reports = [_load_json(path) for path in args.reports]
    reviews = _load_json(args.human_review) if args.human_review else None
    pack = build_evidence_pack(reports, human_reviews=reviews)
    write_evidence_pack(
        pack,
        json_path=args.json_output,
        markdown_path=args.markdown_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
