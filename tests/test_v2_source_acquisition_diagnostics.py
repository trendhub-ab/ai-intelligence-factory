from __future__ import annotations

from datetime import datetime, timezone

import v2_four_source_live as four
import v2_github_live as github
import v2_official_vendor_live as vendor
from v2_live_shadow_acquisition import AcquisitionDiagnostics, bounded_get


class Response:
    status_code = 200

    def raise_for_status(self):
        return None


def test_bounded_get_emits_safe_diagnostic_event_without_url_or_secret():
    events = []

    response, diagnostics = bounded_get(
        http_get=lambda url, **kwargs: Response(),
        url="https://secret.example/path?token=SECRET",
        timeout=1.0,
        diagnostic_sink=events.append,
        sleep_fn=lambda _seconds: None,
    )

    assert response.status_code == 200
    assert diagnostics.attempt_count == 1
    assert events == [
        {
            "attempt_count": 1,
            "retry_used": False,
            "first_failure_category": None,
            "final_failure_category": None,
        }
    ]
    assert "SECRET" not in repr(events)


def test_four_source_live_artifact_aggregates_http_attempts_without_changing_provider_call_count(monkeypatch):
    def candidate(name: str):
        return {
            "url": f"https://example.com/{name}",
            "title": f"AI {name} release",
            "description": "AI API release with deployment and integration changes for production users.",
            "published_at": "2026-10-17T00:00:00Z",
        }

    def vendor(*, diagnostic_sink=None, **kwargs):
        diagnostic_sink(AcquisitionDiagnostics(2, True, "http_5xx", None).as_dict())
        return [candidate("vendor")]

    def github(*, diagnostic_sink=None, **kwargs):
        diagnostic_sink(AcquisitionDiagnostics(1, False, None, None).as_dict())
        return [candidate("github")]

    def hn(*, diagnostic_sink=None, **kwargs):
        diagnostic_sink(AcquisitionDiagnostics(1, False, None, None).as_dict())
        return [candidate("hn")]

    def arxiv(*, diagnostic_sink=None, **kwargs):
        diagnostic_sink(AcquisitionDiagnostics(2, True, "timeout", "timeout").as_dict())
        raise four.SourceAcquisitionError("ArXiv", "timeout")

    monkeypatch.setattr(four, "fetch_all_official_vendor_candidates", vendor)
    monkeypatch.setattr(four, "fetch_all_github_candidates", github)
    monkeypatch.setattr(four, "fetch_hacker_news_candidates", hn)
    monkeypatch.setattr(four, "fetch_arxiv_candidates", arxiv)

    report = four.run_four_source_live(
        deep_dive=lambda _candidate: {"evidence_sufficient": False},
        now=datetime(2026, 10, 17, tzinfo=timezone.utc),
        run_id="aggregate-diagnostic-test",
    )

    assert report["actual_calls"]["provider"] == 4
    diagnostics = report["source_acquisition_diagnostics"]
    assert diagnostics["OfficialVendor"] == {
        "logical_read_count": 1,
        "http_attempt_count": 2,
        "retry_used": True,
        "first_failure_category": "http_5xx",
        "final_failure_category": None,
    }
    assert diagnostics["ArXiv"]["logical_read_count"] == 1
    assert diagnostics["ArXiv"]["http_attempt_count"] == 2
    assert diagnostics["ArXiv"]["retry_used"] is True
    assert diagnostics["ArXiv"]["first_failure_category"] == "timeout"
    assert diagnostics["ArXiv"]["final_failure_category"] == "timeout"
    assert "example.com" not in repr(diagnostics)


class UpstreamResponse:
    status_code = 200

    def __init__(self, url, *, text="", payload=None, status_code=200):
        self.url = url
        self.text = text
        self.payload = [] if payload is None else payload
        self.status_code = status_code

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_vendor_upstream_diagnostics_distinguish_nonempty_empty_http_503_and_invalid_feed():
    events = []
    legacy_events = []
    calls = []

    def http_get(url, **kwargs):
        calls.append(url)
        if url == "https://openai.com/news":
            return UpstreamResponse(url, text='<a href="/index/new-api"><h2>New AI API release</h2></a>')
        if url == "https://www.microsoft.com/en-us/research/blog/":
            return UpstreamResponse(url, status_code=503, text="SECRET_503_BODY")
        if url == "https://developer.nvidia.com/blog/feed/":
            return UpstreamResponse(url, text="<private>SECRET_XML</broken>")
        if url.endswith("rss.xml") or url.endswith("/rss"):
            return UpstreamResponse(url, text="<rss><channel/></rss>")
        return UpstreamResponse(url, text="<html><body></body></html>")

    rows = vendor.fetch_all_official_vendor_candidates(
        http_get=http_get,
        sleep_fn=lambda _: None,
        diagnostic_sink=legacy_events.append,
        upstream_diagnostic_sink=events.append,
    )

    by_source = {event["upstream"]: event for event in events}
    assert list(by_source) == [source.provider for source in vendor.OFFICIAL_VENDOR_SOURCES]
    assert [row["provider"] for row in rows] == ["OpenAI"]
    assert by_source["OpenAI"]["status"] == "success_nonempty"
    assert by_source["OpenAI"]["candidate_count"] == 1
    assert by_source["Anthropic"]["status"] == "success_empty"
    assert by_source["Anthropic"]["candidate_count"] == 0
    assert by_source["Microsoft"]["status"] == "failed"
    assert by_source["Microsoft"]["failure_category"] == "http_5xx"
    assert by_source["Microsoft"]["http_attempt_count"] == 2
    assert by_source["Microsoft"]["retry_used"] is True
    assert by_source["NVIDIA"]["status"] == "failed"
    assert by_source["NVIDIA"]["failure_category"] == "invalid_feed"
    assert by_source["NVIDIA"]["http_attempt_count"] == 1
    assert len(legacy_events) == 8
    assert calls.count("https://www.microsoft.com/en-us/research/blog/") == 2
    assert "SECRET_503_BODY" not in repr(events)
    assert "SECRET_XML" not in repr(events)
    assert "https://" not in repr(events)


def test_github_upstream_diagnostics_distinguish_retry_success_empty_and_invalid_json():
    events = []
    legacy_events = []
    calls = []
    secret = "ghs_SECRET_TOKEN"

    def http_get(url, **kwargs):
        calls.append(url)
        if "openai/openai-python" in url:
            if calls.count(url) == 1:
                return UpstreamResponse(url, status_code=503)
            return UpstreamResponse(url, payload=[{
                "id": 7, "name": "SDK release", "tag_name": "v7",
                "html_url": "https://github.com/openai/openai-python/releases/tag/v7",
                "published_at": "2026-10-17T00:00:00Z",
            }])
        if "googleapis/python-genai" in url:
            return UpstreamResponse(url, payload=ValueError("SECRET_JSON_BODY"))
        return UpstreamResponse(url, payload=[])

    rows = github.fetch_all_github_candidates(
        http_get=http_get,
        token=secret,
        sleep_fn=lambda _: None,
        diagnostic_sink=legacy_events.append,
        upstream_diagnostic_sink=events.append,
    )

    by_source = {event["upstream"]: event for event in events}
    assert list(by_source) == list(github.GITHUB_REPOSITORIES)
    assert [row["repository"] for row in rows] == ["openai/openai-python"]
    assert by_source["openai/openai-python"]["status"] == "success_nonempty"
    assert by_source["openai/openai-python"]["candidate_count"] == 1
    assert by_source["openai/openai-python"]["http_attempt_count"] == 2
    assert by_source["openai/openai-python"]["retry_used"] is True
    assert by_source["openai/openai-python"]["first_failure_category"] == "http_5xx"
    assert by_source["anthropics/anthropic-sdk-python"]["status"] == "success_empty"
    assert by_source["googleapis/python-genai"]["status"] == "failed"
    assert by_source["googleapis/python-genai"]["failure_category"] == "invalid_json"
    assert len(legacy_events) == 3
    assert secret not in repr(events)
    assert "SECRET_JSON_BODY" not in repr(events)
    assert "https://" not in repr(events)


def test_four_source_report_adds_upstream_diagnostics_without_changing_family_contract(monkeypatch):
    def http_get(url, **kwargs):
        if url.startswith("https://api.github.com/"):
            return UpstreamResponse(url, payload=[])
        if url.endswith("rss.xml") or url.endswith("/rss") or url.endswith("/feed/"):
            return UpstreamResponse(url, text="<rss><channel/></rss>")
        return UpstreamResponse(url, text="<html></html>")

    monkeypatch.setattr(four, "fetch_hacker_news_candidates", lambda **kwargs: [])
    monkeypatch.setattr(four, "fetch_arxiv_candidates", lambda **kwargs: [])

    report = four.run_four_source_live(
        http_get=http_get,
        deep_dive=lambda _: {"evidence_sufficient": False},
        now=datetime(2026, 10, 19, tzinfo=timezone.utc),
        run_id="upstream-diag",
    )

    upstreams = report["source_acquisition_upstreams"]
    assert list(upstreams) == ["OfficialVendor", "GitHub"]
    assert list(upstreams["OfficialVendor"]) == [source.provider for source in vendor.OFFICIAL_VENDOR_SOURCES]
    assert list(upstreams["GitHub"]) == list(github.GITHUB_REPOSITORIES)
    assert all(event["status"] == "success_empty" for family in upstreams.values() for event in family.values())
    assert report["source_acquisition_diagnostics"]["OfficialVendor"]["logical_read_count"] == 8
    assert report["source_acquisition_diagnostics"]["GitHub"]["logical_read_count"] == 3
    assert report["actual_calls"]["provider"] == 4
    assert "https://" not in repr(upstreams)
