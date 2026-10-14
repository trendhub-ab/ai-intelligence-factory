from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from v2_live_shadow_acquisition import LiveAcquisitionConfig
from v2_shadow_observation import (
    EvidenceContractError,
    GeminiEvidenceProvider,
    build_provider_backed_observation,
    parse_evidence_result,
    write_observation,
)


NOW = datetime(2026, 10, 14, 3, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, *, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _arxiv_xml(entries: str = "") -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'''


def two_candidate_http_get(url, **kwargs):
    if url.endswith("topstories.json"):
        return FakeResponse(json_data=[101, 102])
    if "/101.json" in url:
        return FakeResponse(
            json_data={
                "id": 101,
                "type": "story",
                "title": "Alpha bounded AI release",
                "url": "https://a.example/releases/alpha",
                "time": 1791940000,
                "score": 180,
                "descendants": 60,
            }
        )
    if "/102.json" in url:
        return FakeResponse(
            json_data={
                "id": 102,
                "type": "story",
                "title": "Beta bounded AI release",
                "url": "https://b.example/releases/beta",
                "time": 1791940000,
                "score": 170,
                "descendants": 55,
            }
        )
    if "export.arxiv.org" in url:
        return FakeResponse(text=_arxiv_xml())
    raise AssertionError(url)


def valid_payload(*, sufficient=True):
    return {
        "evidence_sufficient": sufficient,
        "reason_code": "sufficient_source_evidence" if sufficient else "insufficient_source_evidence",
        "evidence_points": ["The supplied candidate metadata contains a bounded factual signal."],
    }


def test_strict_parser_accepts_only_exact_valid_contract():
    parsed = parse_evidence_result(json.dumps(valid_payload()))
    assert parsed == valid_payload()


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "```json\n{}\n```",
        "[]",
        json.dumps({}),
        json.dumps({**valid_payload(), "extra": 1}),
        json.dumps({**valid_payload(), "evidence_sufficient": 1}),
        json.dumps({**valid_payload(), "reason_code": "maybe"}),
        json.dumps({**valid_payload(), "reason_code": "insufficient_source_evidence"}),
        json.dumps({**valid_payload(), "evidence_points": []}),
        json.dumps({**valid_payload(), "evidence_points": [""]}),
        json.dumps({**valid_payload(), "evidence_points": ["x"] * 6}),
        json.dumps({**valid_payload(), "evidence_points": ["x" * 501]}),
    ],
)
def test_strict_parser_fails_closed_on_malformed_or_ambiguous_results(raw):
    with pytest.raises(EvidenceContractError):
        parse_evidence_result(raw)


def test_false_result_requires_insufficient_reason_code():
    parsed = parse_evidence_result(json.dumps(valid_payload(sufficient=False)))
    assert parsed["evidence_sufficient"] is False
    assert parsed["reason_code"] == "insufficient_source_evidence"


def test_gemini_provider_makes_exactly_one_http_post_and_parses_json():
    calls = []

    def http_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            json_data={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(valid_payload())}]}}
                ]
            }
        )

    provider = GeminiEvidenceProvider(api_key="test-key", http_post=http_post)
    result = provider(
        {
            "candidate_identity": "https://a.example/releases/alpha",
            "provider": "HackerNews",
            "primary_url": "https://a.example/releases/alpha",
            "title": "Alpha bounded AI release",
            "description": "A sufficiently descriptive candidate metadata record for bounded evidence testing.",
            "source_timestamp": "2026-10-14T00:00:00+00:00",
            "screening_score": 60,
            "screening_reasons": ["stable_identity", "description_substantive"],
        }
    )

    assert result == valid_payload()
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert "gemini-3.6-flash:generateContent" in url
    assert "test-key" not in url
    assert kwargs["headers"]["x-goog-api-key"] == "test-key"
    assert kwargs["timeout"] == 120.0
    assert kwargs["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_provider_failure_is_opaque_and_not_retried():
    calls = 0

    def http_post(url, **kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("secret transport detail")

    provider = GeminiEvidenceProvider(api_key="test-key", http_post=http_post)
    with pytest.raises(RuntimeError) as excinfo:
        provider(
            {
                "candidate_identity": "https://a.example/releases/alpha",
                "provider": "HackerNews",
                "primary_url": "https://a.example/releases/alpha",
                "title": "Alpha",
                "description": "bounded description",
                "source_timestamp": None,
                "screening_score": 45,
                "screening_reasons": [],
            }
        )
    assert calls == 1
    assert "secret transport detail" not in str(excinfo.value)


def test_rank1_only_gets_one_deep_dive_and_insufficient_does_not_fallback():
    seen = []

    def deep_dive(candidate):
        seen.append(candidate["candidate_identity"])
        return valid_payload(sufficient=False)

    report = build_provider_backed_observation(
        now=NOW,
        run_id="v2-004-one-shot",
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=0, total_candidate_limit=2),
        http_get=two_candidate_http_get,
        deep_dive=deep_dive,
    )

    assert seen == [report["screening"][0]["candidate_identity"]]
    assert report["deep_dive_attempted_count"] == 1
    assert report["actual_calls"]["deep_dive"] == 1
    assert report["v2_selected_candidate_identity"] is None
    assert report["deep_dive_result_category"] == "insufficient_evidence"
    assert report["observation"]["provider_result"]["evidence_sufficient"] is False


def test_sufficient_rank1_is_shadow_winner_but_v1_remains_authority():
    report = build_provider_backed_observation(
        now=NOW,
        run_id="v2-004-sufficient",
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=0, total_candidate_limit=2),
        http_get=two_candidate_http_get,
        deep_dive=lambda candidate: valid_payload(sufficient=True),
    )

    assert report["v2_selected_candidate_identity"] == report["screening"][0]["candidate_identity"]
    assert report["deep_dive_result_category"] == "sufficient"
    assert report["observation"]["mode"] == "provider_backed_one_shot"
    assert report["observation"]["production_authority"] == "v1"
    assert report["observation"]["diagnostic_only"] is True
    assert report["observation"]["model"] == "gemini-3.6-flash"
    assert report["observation"]["request_budget"] == 1


def test_deep_dive_exception_fails_closed_without_leaking_exception_text():
    calls = 0

    def failing(candidate):
        nonlocal calls
        calls += 1
        raise RuntimeError("private provider payload")

    report = build_provider_backed_observation(
        now=NOW,
        run_id="v2-004-failure",
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=0, total_candidate_limit=2),
        http_get=two_candidate_http_get,
        deep_dive=failing,
    )

    assert calls == 1
    assert report["deep_dive_result_category"] == "provider_failure"
    assert report["failure_category"] == "deep_dive_failure"
    assert report["v2_selected_candidate_identity"] is None
    assert "private provider payload" not in str(report)


def test_write_observation_writes_only_requested_json_path(tmp_path):
    report = build_provider_backed_observation(
        now=NOW,
        run_id="v2-004-write",
        config=LiveAcquisitionConfig(hn_limit=2, arxiv_limit=0, total_candidate_limit=2),
        http_get=two_candidate_http_get,
        deep_dive=lambda candidate: valid_payload(),
    )
    output = tmp_path / "nested" / "deep-dive.json"

    returned = write_observation(report, output)

    assert returned == output
    assert output.is_file()
    files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())
    assert files == ["nested/deep-dive.json"]
    text = output.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert '"provider_backed_one_shot"' in text
