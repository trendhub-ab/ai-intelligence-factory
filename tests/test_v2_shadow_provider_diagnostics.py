from __future__ import annotations

import pytest

from v2_live_shadow_acquisition import LiveAcquisitionConfig
from v2_shadow_observation import (
    GeminiEvidenceError,
    GeminiEvidenceProvider,
    build_provider_backed_observation,
)
from tests.test_v2_shadow_deep_dive import two_candidate_http_get


CANDIDATE = {
    "candidate_identity": "https://a.example/releases/alpha",
    "provider": "HackerNews",
    "primary_url": "https://a.example/releases/alpha",
    "title": "Alpha bounded AI release",
    "description": "A bounded metadata record for provider diagnostics.",
    "source_timestamp": None,
    "screening_score": 60,
    "screening_reasons": ["stable_identity"],
}


def test_provider_timeout_has_safe_machine_code_without_secret_text():
    def http_post(url, **kwargs):
        raise TimeoutError("secret transport detail")

    provider = GeminiEvidenceProvider(api_key="test-key", http_post=http_post)

    with pytest.raises(GeminiEvidenceError) as excinfo:
        provider(CANDIDATE)

    assert excinfo.value.safe_code == "provider_timeout"
    assert "secret transport detail" not in str(excinfo.value)


def test_provider_response_shape_failure_has_safe_machine_code():
    class EmptyCandidateResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": []}

    provider = GeminiEvidenceProvider(
        api_key="test-key",
        http_post=lambda *args, **kwargs: EmptyCandidateResponse(),
    )

    with pytest.raises(GeminiEvidenceError) as excinfo:
        provider(CANDIDATE)

    assert excinfo.value.safe_code == "provider_response_shape_invalid"


def test_artifact_report_records_safe_provider_code_not_exception_class_or_text():
    def failing_deep_dive(candidate):
        raise GeminiEvidenceError("provider_response_shape_invalid")

    report = build_provider_backed_observation(
        now=__import__("datetime").datetime(2026, 10, 14, 5, 0, tzinfo=__import__("datetime").timezone.utc),
        run_id="v2-004-diagnostic",
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=0, total_candidate_limit=2),
        http_get=two_candidate_http_get,
        deep_dive=failing_deep_dive,
    )

    observation = report["observation"]
    assert observation["provider_error_category"] == "provider_response_shape_invalid"
    assert "GeminiEvidenceError" not in str(observation)


def test_evidence_contract_failure_preserves_allowlisted_reason_without_raw_provider_text():
    class InvalidEvidenceResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
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

    report = build_provider_backed_observation(
        now=__import__("datetime").datetime(2026, 10, 16, 5, 0, tzinfo=__import__("datetime").timezone.utc),
        run_id="v2-004-contract-reason",
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=0, total_candidate_limit=2),
        http_get=two_candidate_http_get,
        api_key="test-key",
        http_post=lambda *args, **kwargs: InvalidEvidenceResponse(),
    )

    observation = report["observation"]
    assert report["deep_dive_result_category"] == "provider_failure"
    assert observation["provider_error_category"] == "provider_evidence_contract_invalid"
    assert observation["evidence_contract_reason"] == "reason_code_invalid"
    assert "SECRET_UNSAFE_REASON" not in str(report)
