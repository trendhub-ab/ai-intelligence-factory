from __future__ import annotations

import json

import pytest

from v2_semantic_screening import (
    DEFAULT_SEMANTIC_MODEL,
    GeminiSemanticScreeningProvider,
    SemanticScreeningContractError,
    SemanticScreeningError,
    build_semantic_screening_prompt,
    parse_semantic_screening_result,
)


class FakeResponse:
    def __init__(self, *, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _candidate(identity: str, *, title: str = "Release", description: str = "Concrete source description"):
    return {
        "candidate_identity": identity,
        "provider": "OfficialVendor",
        "primary_url": identity,
        "title": title,
        "description": description,
        "source_timestamp": "2026-10-16T00:00:00+00:00",
        "screening_score": 70,
        "selection_value_score": 0,
        "screening_reasons": ["stable_identity", "title_present"],
    }


def _provider_body(results):
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": json.dumps({"results": results})}
                    ]
                }
            }
        ]
    }


def test_semantic_model_is_current_low_cost_flash_lite():
    assert DEFAULT_SEMANTIC_MODEL == "gemini-3.5-flash-lite"


def test_parse_semantic_screening_result_accepts_exact_bounded_contract():
    expected = [
        {
            "candidate_identity": "https://example.com/a",
            "ai_relevant": True,
            "decision_value": True,
            "change_novelty": False,
            "applied_reader_value": True,
        }
    ]

    parsed = parse_semantic_screening_result(
        json.dumps({"results": expected}),
        expected_identities=["https://example.com/a"],
    )

    assert parsed == {"https://example.com/a": expected[0]}


def test_parse_semantic_screening_result_fails_closed_on_missing_or_extra_identity():
    text = json.dumps(
        {
            "results": [
                {
                    "candidate_identity": "https://example.com/other",
                    "ai_relevant": True,
                    "decision_value": False,
                    "change_novelty": False,
                    "applied_reader_value": False,
                }
            ]
        }
    )

    with pytest.raises(SemanticScreeningContractError, match="result_identities_invalid"):
        parse_semantic_screening_result(text, expected_identities=["https://example.com/a"])


def test_prompt_exposes_source_metadata_but_not_internal_scores_or_reasons():
    prompt = build_semantic_screening_prompt([_candidate("https://example.com/a")])

    assert "https://example.com/a" in prompt
    assert "OfficialVendor" in prompt
    assert "screening_score" not in prompt
    assert "selection_value_score" not in prompt
    assert "screening_reasons" not in prompt


def test_prompt_requires_conservative_evidence_boundaries_for_discrimination():
    prompt = build_semantic_screening_prompt(
        [
            _candidate(
                "https://example.com/roadster",
                title="Tesla Roadster",
                description="HN score=900; comments=400",
            )
        ]
    )

    assert "When evidence is missing, ambiguous, or merely plausible, classify that dimension false." in prompt
    assert "Provider or source identity alone is not evidence" in prompt
    assert "engagement metadata such as scores or comment counts is not semantic evidence" in prompt
    assert "If ai_relevant is false, the other three dimensions must also be false." in prompt
    assert "Do not make every candidate positive merely because this is an AI screening task." in prompt


def test_provider_batches_candidates_into_exactly_one_request():
    calls = []

    def http_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            json_data=_provider_body(
                [
                    {
                        "candidate_identity": "https://example.com/a",
                        "ai_relevant": True,
                        "decision_value": True,
                        "change_novelty": False,
                        "applied_reader_value": True,
                    },
                    {
                        "candidate_identity": "https://example.com/b",
                        "ai_relevant": False,
                        "decision_value": False,
                        "change_novelty": False,
                        "applied_reader_value": False,
                    },
                ]
            )
        )

    provider = GeminiSemanticScreeningProvider(api_key="test-key", http_post=http_post)
    result = provider(
        [
            _candidate("https://example.com/a"),
            _candidate("https://example.com/b"),
        ]
    )

    assert len(calls) == 1
    assert DEFAULT_SEMANTIC_MODEL in calls[0][0]
    assert calls[0][1]["timeout"] > 0
    assert set(result) == {"https://example.com/a", "https://example.com/b"}


def test_provider_rejects_large_all_positive_batch_as_uninformative_saturation():
    identities = [f"https://example.com/{index}" for index in range(10)]

    def http_post(_url, **_kwargs):
        results = [
            {
                "candidate_identity": identity,
                "ai_relevant": True,
                "decision_value": True,
                "change_novelty": True,
                "applied_reader_value": True,
            }
            for identity in identities
        ]
        return FakeResponse(json_data=_provider_body(results))

    provider = GeminiSemanticScreeningProvider(api_key="test-key", http_post=http_post)

    with pytest.raises(SemanticScreeningError) as caught:
        provider([_candidate(identity) for identity in identities])

    assert caught.value.safe_code == "semantic_provider_uninformative_saturated"


def test_provider_classifies_http_5xx_without_leaking_transport_text():
    def http_post(_url, **_kwargs):
        return FakeResponse(status_code=503, json_data={"error": {"message": "private transport text"}})

    provider = GeminiSemanticScreeningProvider(api_key="test-key", http_post=http_post)

    with pytest.raises(SemanticScreeningError) as caught:
        provider([_candidate("https://example.com/a")])

    assert caught.value.safe_code == "semantic_provider_http_5xx"
    assert "private transport text" not in str(caught.value)
