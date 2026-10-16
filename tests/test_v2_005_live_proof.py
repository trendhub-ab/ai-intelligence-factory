from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone

import v2_005_live_proof as live_proof
from v2_four_source_live import FourSourceLiveConfig
from v2_005_live_proof import build_live_proof


NOW = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, *, json_data=None, text="", status_code=200, url=None):
        self._json_data = json_data
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code
        if url is not None:
            self.url = url

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _arxiv_xml(entries: str = "") -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'''


def four_source_http_get(url, **kwargs):
    if url == "https://openai.com/news":
        return FakeResponse(
            url=url,
            text='''<html><body><a href="/index/alpha-ai-release"><h2>AI API release adds enterprise deployment controls</h2></a></body></html>''',
        )
    if url in {
        "https://www.anthropic.com/news",
        "https://blog.google/products-and-platforms/products/gemini/",
    }:
        return FakeResponse(url=url, text="<html><body></body></html>")
    if url == "https://api.github.com/repos/openai/openai-python/releases":
        return FakeResponse(
            url=url,
            json_data=[{
                "id": 123,
                "html_url": "https://github.com/openai/openai-python/releases/tag/v2.0.0",
                "name": "OpenAI Python v2.0.0 AI API release",
                "tag_name": "v2.0.0",
                "body": "AI SDK release improves production deployment workflow, API integration, and enterprise cost.",
                "published_at": "2026-10-15T20:00:00Z",
            }],
        )
    if url in {
        "https://api.github.com/repos/anthropics/anthropic-sdk-python/releases",
        "https://api.github.com/repos/googleapis/python-genai/releases",
    }:
        return FakeResponse(url=url, json_data=[])
    if url.endswith("topstories.json"):
        return FakeResponse(json_data=[101])
    if "/101.json" in url:
        return FakeResponse(
            json_data={
                "id": 101,
                "type": "story",
                "title": "Bounded AI release improves deployment",
                "url": "https://a.example/releases/alpha",
                "time": 1792020000,
                "score": 180,
                "descendants": 60,
            }
        )
    if "export.arxiv.org" in url:
        return FakeResponse(text=_arxiv_xml())
    raise AssertionError(url)


def _evidence_body(*, sufficient=True, usage=None):
    evidence = {
        "evidence_sufficient": sufficient,
        "reason_code": "sufficient_source_evidence" if sufficient else "insufficient_source_evidence",
        "evidence_points": ["The supplied metadata contains a bounded factual signal."],
    }
    body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(evidence)}]}}
        ]
    }
    if usage is not None:
        body["usageMetadata"] = usage
    return body


def _semantic_body_from_request(kwargs, *, usage=None):
    prompt = kwargs["json"]["contents"][0]["parts"][0]["text"]
    candidates = json.loads(prompt.split("Candidates:\n", 1)[1])
    results = [
        {
            "candidate_identity": candidate["candidate_identity"],
            "ai_relevant": True,
            "decision_value": True,
            "change_novelty": True,
            "applied_reader_value": True,
        }
        for candidate in candidates
    ]
    body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps({"results": results})}]}}
        ]
    }
    if usage is not None:
        body["usageMetadata"] = usage
    return body


def _build(*, post_response):
    post_calls = []

    def http_post(url, **kwargs):
        post_calls.append((url, kwargs))
        if "gemini-3.5-flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        return post_response

    report = build_live_proof(
        now=NOW,
        run_id="v2-005c-test",
        api_key="SECRET_KEY",
        config=FourSourceLiveConfig(
            vendor_limit=5,
            github_limit=5,
            hn_limit=1,
            arxiv_limit=0,
            max_total_candidates=8,
        ),
        http_get=four_source_http_get,
        http_post=http_post,
    )
    return report, post_calls


def test_live_proof_routes_through_four_source_bridge_not_old_two_source_builder():
    source = inspect.getsource(live_proof.build_live_proof)
    assert "run_four_source_live" in source
    assert "build_provider_backed_observation" not in source


def test_live_proof_records_safe_rank1_measurement_with_two_bounded_model_requests():
    report, post_calls = _build(post_response=FakeResponse(json_data=_evidence_body()))

    assert len(post_calls) == 2
    assert "gemini-3.5-flash-lite:generateContent" in post_calls[0][0]
    assert "gemini-3.6-flash:generateContent" in post_calls[1][0]
    assert post_calls[1][1]["timeout"] == 120.0
    measurement = report["v2_005_measurement"]
    assert report["v2_selected_candidate_identity"] == measurement["evaluated_candidate"]["candidate_identity"]
    assert measurement["proof_version"] == "V2-005"
    assert measurement["production_mutation_authorized"] is False
    assert measurement["promotion_decision"] == "human_review_required"
    assert set(measurement["evaluated_candidate"]) == {
        "candidate_identity",
        "provider",
        "title",
        "source_timestamp",
        "screening_score",
        "screening_reasons",
    }
    assert measurement["semantic_provider_request_count"] == 1
    assert measurement["provider_request_count"] == 1
    assert measurement["total_model_request_count"] == 2
    assert report["actual_calls"]["semantic_screen"] == 1
    assert report["actual_calls"]["deep_dive"] == 1
    assert report["live_acquisition"]["source_families"] == [
        "official_vendor",
        "github",
        "hacker_news",
        "arxiv",
    ]


def test_live_proof_records_numeric_evidence_provider_usage_when_present():
    report, _ = _build(
        post_response=FakeResponse(
            json_data=_evidence_body(
                usage={
                    "promptTokenCount": 123,
                    "candidatesTokenCount": 45,
                    "totalTokenCount": 168,
                }
            )
        )
    )
    assert report["v2_005_measurement"]["provider_usage"] == {
        "prompt_token_count": 123,
        "candidate_token_count": 45,
        "total_token_count": 168,
    }
    assert report["v2_005_measurement"]["semantic_provider_usage"] is None


def test_live_proof_tolerates_missing_usage_metadata():
    report, _ = _build(post_response=FakeResponse(json_data=_evidence_body()))
    assert report["deep_dive_result_category"] == "sufficient"
    assert report["v2_005_measurement"]["provider_usage"] is None


def test_live_proof_tolerates_malformed_usage_metadata():
    report, _ = _build(
        post_response=FakeResponse(
            json_data=_evidence_body(
                usage={
                    "promptTokenCount": 123,
                    "candidatesTokenCount": "45",
                    "totalTokenCount": 168,
                }
            )
        )
    )
    assert report["deep_dive_result_category"] == "sufficient"
    assert report["v2_005_measurement"]["provider_usage"] is None


def test_live_proof_does_not_persist_raw_source_html_prompt_key_headers_or_raw_provider_body():
    def secret_http_get(url, **kwargs):
        if url == "https://openai.com/news":
            return FakeResponse(
                url=url,
                text='<html><body><!-- SECRET_VENDOR_HTML --><a href="/index/release"><h2>AI API release improves deployment</h2></a></body></html>',
            )
        if url in {
            "https://www.anthropic.com/news",
            "https://blog.google/products-and-platforms/products/gemini/",
        }:
            return FakeResponse(url=url, text="<html><body></body></html>")
        if url.startswith("https://api.github.com/repos/"):
            return FakeResponse(url=url, json_data=[])
        if url.endswith("topstories.json"):
            return FakeResponse(json_data=[])
        if "export.arxiv.org" in url:
            return FakeResponse(text=_arxiv_xml())
        raise AssertionError(url)

    def http_post(url, **kwargs):
        if "gemini-3.5-flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        body = _evidence_body()
        body["providerDebug"] = "SECRET_PROVIDER_BODY"
        return FakeResponse(json_data=body)

    report = build_live_proof(
        now=NOW,
        run_id="v2-005c-secret-test",
        api_key="SECRET_KEY",
        config=FourSourceLiveConfig(hn_limit=0, arxiv_limit=0, max_total_candidates=5),
        http_get=secret_http_get,
        http_post=http_post,
    )
    serialized = json.dumps(report, ensure_ascii=False)
    assert "SECRET_VENDOR_HTML" not in serialized
    assert "SECRET_KEY" not in serialized
    assert "SECRET_PROVIDER_BODY" not in serialized
    assert "x-goog-api-key" not in serialized
    assert "Candidates:" not in serialized
    assert "Candidate metadata" not in serialized


def test_lite_failure_falls_back_without_blocking_flash_evidence():
    post_calls = []

    def http_post(url, **kwargs):
        post_calls.append(url)
        if "gemini-3.5-flash-lite" in url:
            return FakeResponse(json_data={"error": "SECRET_LITE_BODY"}, status_code=503)
        return FakeResponse(json_data=_evidence_body())

    report = build_live_proof(
        now=NOW,
        run_id="v2-lite-fallback",
        api_key="SECRET_KEY",
        config=FourSourceLiveConfig(hn_limit=1, arxiv_limit=0, max_total_candidates=8),
        http_get=four_source_http_get,
        http_post=http_post,
    )

    assert len(post_calls) == 2
    assert report["semantic_screening"] == {"status": "provider_failure", "fallback_used": True}
    assert report["observation"]["semantic_provider_error_category"] == "semantic_provider_http_5xx"
    assert report["deep_dive_result_category"] == "sufficient"
    assert report["v2_selected_candidate_identity"] is not None
    assert "SECRET_LITE_BODY" not in json.dumps(report)


def test_live_proof_preserves_safe_evidence_provider_failure_classification_without_retry():
    post_calls = 0

    def http_post(url, **kwargs):
        nonlocal post_calls
        post_calls += 1
        if "gemini-3.5-flash-lite" in url:
            return FakeResponse(json_data=_semantic_body_from_request(kwargs))
        return FakeResponse(json_data={"error": "SECRET_PROVIDER_BODY"}, status_code=429)

    report = build_live_proof(
        now=NOW,
        run_id="v2-005c-429",
        api_key="SECRET_KEY",
        config=FourSourceLiveConfig(hn_limit=1, arxiv_limit=0, max_total_candidates=8),
        http_get=four_source_http_get,
        http_post=http_post,
    )
    assert post_calls == 2
    assert report["deep_dive_result_category"] == "provider_failure"
    assert report["observation"]["provider_error_category"] == "provider_http_429"
    assert report["v2_selected_candidate_identity"] is None
    assert "SECRET_PROVIDER_BODY" not in json.dumps(report)


def test_live_proof_insufficient_rank1_never_rescues_rank2():
    report, post_calls = _build(
        post_response=FakeResponse(json_data=_evidence_body(sufficient=False))
    )
    assert len(post_calls) == 2
    assert report["deep_dive_result_category"] == "insufficient_evidence"
    assert report["v2_selected_candidate_identity"] is None


def test_live_proof_keeps_v1_authority_and_diagnostic_only_boundary():
    report, _ = _build(post_response=FakeResponse(json_data=_evidence_body()))
    assert report["observation"]["mode"] == "provider_backed_one_shot"
    assert report["observation"]["production_authority"] == "v1"
    assert report["observation"]["diagnostic_only"] is True
    assert report["observation"]["semantic_request_budget"] == 1
    assert report["observation"]["semantic_model"] == "gemini-3.5-flash-lite"
    assert report["observation"]["request_budget"] == 1
    assert report["observation"]["model"] == "gemini-3.6-flash"
    assert report["observation"]["total_model_request_budget"] == 2
    assert report["actual_calls"]["semantic_screen"] <= 1
    assert report["actual_calls"]["deep_dive"] <= 1
    assert report["v2_005_measurement"]["production_mutation_authorized"] is False
