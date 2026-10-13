from __future__ import annotations

from datetime import datetime, timezone

from v2_live_shadow_acquisition import LiveAcquisitionConfig, run_bounded_live_shadow


FIXED_NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


class FixtureResponse:
    def __init__(self, *, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("fixture HTTP failure")


def fixture_http_get(url, **kwargs):
    if url.endswith("topstories.json"):
        return FixtureResponse(json_data=[1001, 1002])
    if "/1001.json" in url:
        return FixtureResponse(json_data={
            "id": 1001,
            "type": "story",
            "title": "AI systems release improves local inference",
            "url": "https://vendor.example/releases/local-inference",
            "time": 1791930000,
            "score": 120,
            "descendants": 42,
        })
    if "/1002.json" in url:
        return FixtureResponse(json_data={
            "id": 1002,
            "type": "story",
            "title": "A second implementation note",
            "url": "https://engineering.example/posts/implementation-note",
            "time": 1791929000,
            "score": 80,
            "descendants": 12,
        })
    if "export.arxiv.org" in url:
        return FixtureResponse(text='''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>https://arxiv.org/abs/2610.01001v1</id>
            <published>2026-10-13T12:00:00Z</published>
            <title>Robust Evaluation of Small Language Models</title>
            <summary>This paper presents a reproducible evaluation framework for small language models under constrained inference budgets and reports controlled benchmark measurements.</summary>
          </entry>
          <entry>
            <id>https://arxiv.org/abs/2610.01002v1</id>
            <published>2026-10-13T11:00:00Z</published>
            <title>Efficient Tool Use for Autonomous Agents</title>
            <summary>This work studies bounded tool-use policies for autonomous agents and evaluates reliability across several controlled task environments.</summary>
          </entry>
        </feed>''')
    raise AssertionError(f"unexpected URL: {url}")


def run_fixture():
    deep_dive_calls = []

    def deep_dive(candidate):
        deep_dive_calls.append(candidate["candidate_identity"])
        return {"evidence_sufficient": True}

    report = run_bounded_live_shadow(
        http_get=fixture_http_get,
        deep_dive=deep_dive,
        config=LiveAcquisitionConfig(
            hn_limit=2,
            arxiv_limit=2,
            total_candidate_limit=4,
            timeout_seconds=2,
        ),
        now=FIXED_NOW,
        run_id="v2-002-fixture",
        v1_reference="https://different.example/v1-selected",
    )
    return report, deep_dive_calls
