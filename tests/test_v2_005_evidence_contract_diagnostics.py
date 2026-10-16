from __future__ import annotations

import json

import pytest

from v2_005_live_proof import build_live_proof
from v2_four_source_live import FourSourceLiveConfig
from v2_shadow_observation import GeminiEvidenceError
from tests.test_v2_005_live_proof import (
    FakeResponse,
    NOW,
    _semantic_body_from_request,
    four_source_http_get,
)


def test_live_proof_preserves_allowlisted_evidence_contract_reason_without_raw_text():
    post_calls = 0

    def http_post(url, **kwargs):
        nonlocal post_calls
        post_calls += 1
        if "gemini-3.5-flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        return FakeResponse(
            json_data={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"evidence_sufficient":true,'
                                        '"reason_code":"SECRET_UNSAFE_REASON",'
                                        '"evidence_points":["bounded point"]}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        )

    report = build_live_proof(
        now=NOW,
        run_id="v2-005-contract-reason",
        api_key="SECRET_KEY",
        config=FourSourceLiveConfig(hn_limit=1, arxiv_limit=0, max_total_candidates=8),
        http_get=four_source_http_get,
        http_post=http_post,
    )

    assert post_calls == 2
    assert report["semantic_screening"]["status"] == "success"
    assert report["deep_dive_result_category"] == "provider_failure"
    assert report["observation"]["provider_error_category"] == "provider_evidence_contract_invalid"
    assert report["observation"]["evidence_contract_reason"] == "reason_code_invalid"
    assert report["v2_selected_candidate_identity"] is None
    assert "SECRET_UNSAFE_REASON" not in json.dumps(report, ensure_ascii=False)


def test_gemini_evidence_error_rejects_unallowlisted_contract_reason():
    with pytest.raises(ValueError, match="unsupported evidence contract reason"):
        GeminiEvidenceError(
            "provider_evidence_contract_invalid",
            evidence_contract_reason="SECRET_UNSAFE_REASON",
        )


def test_gemini_evidence_error_rejects_contract_reason_on_non_contract_error():
    with pytest.raises(ValueError, match="requires evidence contract error"):
        GeminiEvidenceError(
            "provider_timeout",
            evidence_contract_reason="reason_code_invalid",
        )