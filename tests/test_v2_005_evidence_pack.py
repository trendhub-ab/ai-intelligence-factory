from __future__ import annotations

import json

import pytest

from v2_005_evidence_pack import (
    EvidencePackContractError,
    _load_json,
    build_evidence_pack,
    main,
    render_evidence_pack_markdown,
    write_evidence_pack,
)


EVIDENCE_POOL = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3-flash-preview",
]


def _usage(prompt: int = 100, candidate: int = 20, total: int = 120):
    return {
        "prompt_token_count": prompt,
        "candidate_token_count": candidate,
        "total_token_count": total,
    }


def _valid_report(
    run_id: str,
    *,
    outcome: str = "sufficient",
    usage=None,
    provider_error: str | None = None,
    provider_requests: int | None = None,
    selected_model: str | None = None,
):
    sufficient = outcome == "sufficient"
    attempted = 0 if outcome == "not_attempted" else 1
    if provider_requests is None:
        provider_requests = 0 if attempted == 0 else 1
    provider_result = None
    if outcome in {"sufficient", "insufficient_evidence"}:
        provider_result = {
            "evidence_sufficient": sufficient,
            "reason_code": (
                "sufficient_source_evidence"
                if sufficient
                else "insufficient_source_evidence"
            ),
            "evidence_points": [f"{run_id} bounded evidence point"],
        }
        selected_model = selected_model or EVIDENCE_POOL[0]
    elif selected_model is None:
        selected_model = None

    identity = f"https://v2.example/{run_id}"
    return {
        "run_id": run_id,
        "timestamp": "2026-10-15T00:00:00+00:00",
        "mode": "shadow",
        "deep_dive_result_category": outcome,
        "v2_selected_candidate_identity": identity if sufficient else None,
        "failure_category": None if sufficient else "insufficient_evidence",
        "actual_calls": {
            "provider": 2,
            "deep_dive": attempted,
        },
        "observation": {
            "mode": "provider_backed_one_shot",
            "evidence_model_pool": list(EVIDENCE_POOL),
            "model": selected_model or EVIDENCE_POOL[0],
            "selected_evidence_model": selected_model,
            "request_budget": 5,
            "provider_result": provider_result,
            "provider_error_category": provider_error,
            "production_authority": "v1",
            "diagnostic_only": True,
        },
        "v2_005_measurement": {
            "proof_version": "V2-005",
            "evaluated_candidate": (
                {
                    "candidate_identity": identity,
                    "provider": "HackerNews",
                    "title": f"Candidate {run_id}",
                    "source_timestamp": "2026-10-15T00:00:00+00:00",
                    "screening_score": 55,
                    "screening_reasons": [
                        "stable_identity",
                        "title_present",
                        "fresh_within_7d",
                    ],
                }
                if attempted
                else None
            ),
            "provider_usage": usage,
            "provider_request_count": provider_requests,
            "production_mutation_authorized": False,
            "promotion_decision": "human_review_required",
        },
    }


def _three_reports():
    return [
        _valid_report("run-1", outcome="sufficient", usage=_usage(100, 20, 120)),
        _valid_report(
            "run-2",
            outcome="insufficient_evidence",
            usage=_usage(90, 10, 100),
            provider_requests=2,
            selected_model="gemini-3.5-flash",
        ),
        _valid_report(
            "run-3",
            outcome="provider_failure",
            usage=None,
            provider_error="provider_http_429",
            provider_requests=5,
        ),
    ]


def test_evidence_pack_accepts_three_valid_unique_runs():
    pack = build_evidence_pack(_three_reports())

    assert pack["proof_version"] == "V2-005"
    assert pack["run_count"] == 3
    assert pack["promotion_decision"] == "human_review_required"


def test_evidence_pack_accepts_five_valid_unique_runs():
    reports = _three_reports() + [
        _valid_report("run-4", outcome="not_attempted"),
        _valid_report("run-5", outcome="insufficient_evidence", usage=_usage()),
    ]

    pack = build_evidence_pack(reports)

    assert pack["run_count"] == 5


def test_evidence_pack_rejects_fewer_than_three_runs():
    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(_three_reports()[:2])


def test_evidence_pack_rejects_more_than_five_runs():
    reports = _three_reports() + [
        _valid_report("run-4"),
        _valid_report("run-5"),
        _valid_report("run-6"),
    ]

    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(reports)


def test_evidence_pack_rejects_duplicate_run_ids():
    reports = _three_reports()
    reports[2]["run_id"] = "run-1"

    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(reports)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("observation", "mode"), "manual_zero_model"),
        (("observation", "production_authority"), "v2"),
        (("observation", "diagnostic_only"), False),
        (("observation", "request_budget"), 4),
        (("actual_calls", "deep_dive"), 2),
        (("v2_005_measurement", "provider_request_count"), 6),
        (("v2_005_measurement", "production_mutation_authorized"), True),
        (("v2_005_measurement", "promotion_decision"), "approved"),
    ],
)
def test_evidence_pack_rejects_any_run_without_v1_shadow_safety_proof(path, value):
    reports = _three_reports()
    target = reports[1]
    cursor = target
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value

    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(reports)


def test_evidence_pack_accepts_multiple_provider_attempts_for_one_logical_deep_dive():
    reports = _three_reports()
    reports[0]["v2_005_measurement"]["provider_request_count"] = 4
    reports[0]["observation"]["selected_evidence_model"] = "gemini-3.8-flash"
    reports[0]["observation"]["model"] = "gemini-3.8-flash"

    pack = build_evidence_pack(reports)

    row = next(item for item in pack["runs"] if item["run_id"] == "run-1")
    assert row["provider_request_count"] == 4


def test_evidence_pack_rejects_zero_provider_attempts_for_attempted_deep_dive():
    reports = _three_reports()
    reports[1]["v2_005_measurement"]["provider_request_count"] = 0

    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(reports)


def test_evidence_pack_rejects_non_v1_evidence_pool():
    reports = _three_reports()
    reports[0]["observation"]["evidence_model_pool"] = ["gemini-3.6-flash"]

    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(reports)


def test_evidence_pack_aggregates_winners_evidence_failures_requests_and_tokens():
    pack = build_evidence_pack(_three_reports())

    assert pack["proof_version"] == "V2-005"
    assert pack["run_count"] == 3
    assert pack["winner_count"] == 1
    assert pack["evidence_sufficient_count"] == 1
    assert pack["evidence_insufficient_count"] == 1
    assert pack["provider_failure_count"] == 1
    assert pack["provider_request_count_total"] == 8
    assert pack["provider_usage_observed_run_count"] == 2
    assert pack["provider_usage_totals"] == {
        "prompt_token_count": 190,
        "candidate_token_count": 30,
        "total_token_count": 220,
    }
    assert pack["provider_error_counts"] == {"provider_http_429": 1}
    assert [row["run_id"] for row in pack["runs"]] == ["run-1", "run-2", "run-3"]
    assert pack["promotion_decision"] == "human_review_required"
    assert "cost" not in json.dumps(pack, ensure_ascii=False).lower()


def test_evidence_pack_accepts_and_normalizes_valid_human_review():
    reviews = {
        "run-1": {
            "v1_candidate_identity": "https://v1.example/item",
            "verdict": "v2_better",
            "rationale": "  clearer   evidence  ",
        }
    }

    pack = build_evidence_pack(_three_reports(), human_reviews=reviews)
    row = next(item for item in pack["runs"] if item["run_id"] == "run-1")

    assert row["review_status"] == "reviewed"
    assert row["human_review"] == {
        "v1_candidate_identity": "https://v1.example/item",
        "verdict": "v2_better",
        "rationale": "clearer evidence",
    }


def test_evidence_pack_rejects_human_review_for_unknown_run():
    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(
            _three_reports(),
            human_reviews={
                "run-99": {
                    "v1_candidate_identity": None,
                    "verdict": "not_comparable",
                    "rationale": "No comparable V1 candidate.",
                }
            },
        )


def test_evidence_pack_rejects_invalid_human_review_verdict():
    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(
            _three_reports(),
            human_reviews={
                "run-1": {
                    "v1_candidate_identity": None,
                    "verdict": "approved",
                    "rationale": "Looks good.",
                }
            },
        )


@pytest.mark.parametrize("rationale", [123, "x" * 1001])
def test_evidence_pack_rejects_invalid_human_review_rationale(rationale):
    with pytest.raises(EvidencePackContractError):
        build_evidence_pack(
            _three_reports(),
            human_reviews={
                "run-1": {
                    "v1_candidate_identity": None,
                    "verdict": "not_comparable",
                    "rationale": rationale,
                }
            },
        )


def test_evidence_pack_marks_missing_human_review_as_not_reviewed():
    pack = build_evidence_pack(_three_reports())

    assert all(row["review_status"] == "not_reviewed" for row in pack["runs"])
    assert all(row["human_review"] is None for row in pack["runs"])


def test_evidence_pack_is_deterministic_across_input_order():
    reports = _three_reports()

    assert build_evidence_pack(reports) == build_evidence_pack(list(reversed(reports)))


def test_evidence_pack_markdown_is_deterministic_and_never_authorizes_promotion():
    pack = build_evidence_pack(_three_reports())

    first = render_evidence_pack_markdown(pack)
    second = render_evidence_pack_markdown(pack)

    assert first == second
    assert first.splitlines()[-1] == (
        "Promotion decision: HUMAN REVIEW REQUIRED — "
        "this evidence pack cannot authorize V2-006 automatically."
    )


def test_evidence_pack_writer_creates_only_requested_deterministic_files(tmp_path):
    pack = build_evidence_pack(_three_reports())
    json_path = tmp_path / "nested" / "evidence-pack.json"
    markdown_path = tmp_path / "nested" / "evidence-pack.md"

    returned = write_evidence_pack(
        pack,
        json_path=json_path,
        markdown_path=markdown_path,
    )

    assert returned == (json_path, markdown_path)
    assert json_path.is_file()
    assert markdown_path.is_file()
    files = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert files == ["nested/evidence-pack.json", "nested/evidence-pack.md"]
    assert json.loads(json_path.read_text(encoding="utf-8")) == pack
    assert json_path.read_text(encoding="utf-8").endswith("\n")
    assert markdown_path.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.parametrize(
    "payload",
    [
        '{"run_id":"run-1","run_id":"run-2"}',
        '{"observation":{"diagnostic_only":true,"diagnostic_only":false}}',
        '{"human_review":{"verdict":"v2_better","verdict":"v1_better"}}',
        '{"run_id":"run-1","\\u0072un_id":"run-2"}',
    ],
)
def test_evidence_pack_json_reader_rejects_duplicate_keys_at_any_depth(tmp_path, payload):
    input_path = tmp_path / "duplicate.json"
    input_path.write_text(payload, encoding="utf-8")

    with pytest.raises(EvidencePackContractError, match="evidence_pack_json_duplicate_key"):
        _load_json(input_path)


def test_evidence_pack_cli_rejects_duplicate_run_id_before_writing(tmp_path, monkeypatch):
    paths = []
    for index, report in enumerate(_three_reports()):
        serialized = json.dumps(report)
        if index == 0:
            serialized = serialized[:-1] + ', "run_id": "renamed-run"}'
        input_path = tmp_path / f"run-{index}.json"
        input_path.write_text(serialized, encoding="utf-8")
        paths.append(input_path)

    json_output = tmp_path / "evidence-pack.json"
    markdown_output = tmp_path / "evidence-pack.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "v2_005_evidence_pack.py",
            *(str(path) for path in paths),
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ],
    )

    with pytest.raises(EvidencePackContractError, match="evidence_pack_json_duplicate_key"):
        main()

    assert not json_output.exists()
    assert not markdown_output.exists()
