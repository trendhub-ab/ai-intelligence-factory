from __future__ import annotations

from datetime import datetime, timezone

import v2_four_source_live as four
from v2_live_shadow_acquisition import AcquisitionDiagnostics, bounded_get
from v2_shadow_selection import ShadowConfig, run_shadow_selection


class Response:
    status_code = 200

    def raise_for_status(self):
        return None


class SafeSourceError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__("SECRET_TRANSPORT_DETAIL")


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


def test_shadow_provider_status_prefers_safe_category_attribute_not_exception_class_or_message():
    def broken_provider():
        raise SafeSourceError("http_503")

    report = run_shadow_selection(
        providers={"ArXiv": broken_provider},
        deep_dive=lambda _candidate: {"evidence_sufficient": False},
        config=ShadowConfig(max_candidates_per_provider=5, max_deep_dive_attempts=1),
        now=datetime(2026, 10, 17, tzinfo=timezone.utc),
        run_id="diagnostic-test",
    )

    assert report["provider_statuses"]["ArXiv"]["error_category"] == "http_503"
    assert "SECRET_TRANSPORT_DETAIL" not in repr(report)


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
