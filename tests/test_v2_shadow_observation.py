from __future__ import annotations

from datetime import datetime, timezone

from v2_live_shadow_acquisition import LiveAcquisitionConfig
from v2_shadow_observation import (
    build_manual_observation,
    derive_pre_deep_dive_leader,
    write_observation,
)


NOW = datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc)


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


def healthy_http_get(url, **kwargs):
    if url.endswith("topstories.json"):
        return FakeResponse(json_data=[101])
    if "/101.json" in url:
        return FakeResponse(
            json_data={
                "id": 101,
                "type": "story",
                "title": "Bounded AI systems release",
                "url": "https://vendor.example/releases/bounded-ai",
                "time": 1791930000,
                "score": 150,
                "descendants": 50,
            }
        )
    if "export.arxiv.org" in url:
        return FakeResponse(text=_arxiv_xml())
    raise AssertionError(url)


def test_manual_observation_is_zero_model_and_never_claims_winner():
    report = build_manual_observation(
        now=NOW,
        run_id="v2-003-test",
        config=LiveAcquisitionConfig(hn_limit=1, arxiv_limit=1, total_candidate_limit=2),
        http_get=healthy_http_get,
    )

    assert report["mode"] == "shadow"
    assert report["observation"]["mode"] == "manual_zero_model"
    assert report["deep_dive_attempted_count"] == 0
    assert report["actual_calls"]["deep_dive"] == 0
    assert report["v2_selected_candidate_identity"] is None
    assert report["comparison_status"] == "v2_no_winner"


def test_pre_deep_dive_leader_contains_only_existing_screening_fields():
    report = build_manual_observation(
        now=NOW,
        run_id="v2-003-leader",
        config=LiveAcquisitionConfig(hn_limit=1, arxiv_limit=1, total_candidate_limit=2),
        http_get=healthy_http_get,
    )

    leader = report["pre_deep_dive_leader"]
    assert leader == {
        "candidate_identity": "https://vendor.example/releases/bounded-ai",
        "provider": "HackerNews",
        "screening_score": report["screening"][0]["screening_score"],
        "eligible": report["screening"][0]["eligible"],
    }
    assert set(leader) == {"candidate_identity", "provider", "screening_score", "eligible"}
    assert derive_pre_deep_dive_leader(report) == leader


def test_empty_screening_has_no_pre_deep_dive_leader():
    def empty_http_get(url, **kwargs):
        if url.endswith("topstories.json"):
            return FakeResponse(json_data=[])
        if "export.arxiv.org" in url:
            return FakeResponse(text=_arxiv_xml())
        raise AssertionError(url)

    report = build_manual_observation(
        now=NOW,
        run_id="v2-003-empty",
        config=LiveAcquisitionConfig(hn_limit=1, arxiv_limit=1, total_candidate_limit=2),
        http_get=empty_http_get,
    )

    assert report["pre_deep_dive_leader"] is None
    assert report["v2_selected_candidate_identity"] is None
    assert report["deep_dive_attempted_count"] == 0


def test_one_source_failure_is_observed_without_raising_or_leaking_transport_text():
    def http_get(url, **kwargs):
        if url.endswith("topstories.json"):
            return FakeResponse(json_data=[101])
        if "/101.json" in url:
            return FakeResponse(
                json_data={
                    "id": 101,
                    "type": "story",
                    "title": "Surviving AI release",
                    "url": "https://vendor.example/releases/survives",
                    "time": 1791930000,
                    "score": 120,
                    "descendants": 20,
                }
            )
        if "export.arxiv.org" in url:
            raise TimeoutError("do not leak this text")
        raise AssertionError(url)

    report = build_manual_observation(
        now=NOW,
        run_id="v2-003-partial",
        config=LiveAcquisitionConfig(hn_limit=1, arxiv_limit=1, total_candidate_limit=2),
        http_get=http_get,
    )

    assert report["provider_statuses"]["HackerNews"]["status"] == "success"
    assert report["provider_statuses"]["ArXiv"]["status"] == "failure"
    assert report["deep_dive_attempted_count"] == 0
    assert "do not leak this text" not in str(report)


def test_both_source_failure_is_valid_fail_closed_observation():
    def http_get(url, **kwargs):
        raise TimeoutError("opaque source detail")

    report = build_manual_observation(
        now=NOW,
        run_id="v2-003-all-down",
        config=LiveAcquisitionConfig(hn_limit=1, arxiv_limit=1, total_candidate_limit=2),
        http_get=http_get,
    )

    assert report["failure_category"] == "all_providers_failed"
    assert report["pre_deep_dive_leader"] is None
    assert report["v2_selected_candidate_identity"] is None
    assert report["deep_dive_attempted_count"] == 0


def test_write_observation_writes_only_requested_json_path(tmp_path):
    report = build_manual_observation(
        now=NOW,
        run_id="v2-003-write",
        config=LiveAcquisitionConfig(hn_limit=1, arxiv_limit=1, total_candidate_limit=2),
        http_get=healthy_http_get,
    )
    output = tmp_path / "nested" / "observation.json"

    returned = write_observation(report, output)

    assert returned == output
    assert output.is_file()
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()) == [
        "nested/observation.json"
    ]
    text = output.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert '"manual_zero_model"' in text
