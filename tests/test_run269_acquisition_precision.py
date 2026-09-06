from __future__ import annotations

from types import SimpleNamespace
import unittest

from run269_acquisition_precision import (
    HN_AI_QUERIES,
    HN_LOOKBACK_DAYS,
    OFFICIAL_VENDOR_REGISTRY,
    _query_matches_title,
    fetch_hackernews_ai_reactions,
    fetch_official_vendor_updates,
)
from run269_business_source_precision import install
from source_normalization import normalize_item


class FakeResponse:
    def __init__(self, *, text="", payload=None, url="https://example.com/"):
        self.text = text
        self._payload = payload if payload is not None else {}
        self.url = url
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class Run269PrecisionTests(unittest.TestCase):
    def test_registry_preserves_three_us_and_eight_cn_vendors(self):
        self.assertEqual(11, len(OFFICIAL_VENDOR_REGISTRY))
        self.assertEqual(3, sum(1 for row in OFFICIAL_VENDOR_REGISTRY if row["region"] == "US"))
        self.assertEqual(8, sum(1 for row in OFFICIAL_VENDOR_REGISTRY if row["region"] == "CN"))
        names = {row["vendor"] for row in OFFICIAL_VENDOR_REGISTRY}
        self.assertIn("Moonshot AI Kimi", names)
        self.assertIn("MiniMax", names)
        self.assertIn("Tencent Hunyuan", names)

    def test_raw_ai_query_is_not_part_of_precision_contract(self):
        self.assertNotIn("AI", HN_AI_QUERIES)
        self.assertEqual(30, HN_LOOKBACK_DAYS)

    def test_exact_query_match_rejects_qwen_jquery_typo(self):
        self.assertFalse(_query_matches_title("Twenty Years of jQuery: How a Little Library Rewired Web Development", "Qwen"))
        self.assertTrue(_query_matches_title("Show HN: Qwen 3.5 runs locally", "Qwen"))
        self.assertTrue(_query_matches_title("A large language model from scratch", '"large language model"'))

    def test_hn_fetch_postfilters_algolia_typo_matches(self):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(kwargs["params"])
            return FakeResponse(
                payload={
                    "hits": [
                        {"objectID": "bad", "title": "Twenty Years of jQuery", "url": "https://example.com/jquery", "points": 100, "num_comments": 50, "created_at_i": 1788700000},
                        {"objectID": "good", "title": "Qwen 3.5 inference notes", "url": "https://example.com/qwen", "points": 10, "num_comments": 5, "created_at_i": 1788700001},
                    ]
                },
                url=url,
            )

        rows = fetch_hackernews_ai_reactions(
            5,
            normalize_item=normalize_item,
            http_get=fake_get,
            queries=("Qwen",),
        )
        self.assertEqual(["good"], [row["sourceDetails"]["hn_id"] for row in rows])
        self.assertEqual("title", calls[0]["restrictSearchableAttributes"])
        self.assertTrue(calls[0]["numericFilters"].startswith("created_at_i>"))
        self.assertEqual("Qwen", rows[0]["sourceDetails"]["matched_query"])
        self.assertTrue(rows[0]["sourceDetails"]["run269_precision"])

    def test_pre_h1_navigation_is_not_promoted(self):
        registry = (
            {"vendor": "TestVendor", "region": "US", "release_url": "https://example.com/releases", "allowed_domains": ("example.com",)},
        )
        html = (
            '<a href="/pricing">Models & pricing</a><a href="/key">Get API key</a>'
            '<h1>Release notes</h1><h2>Sep 3, 2026</h2>'
            '<h3>Introducing Model-X2</h3><p>Model-X2 is now generally available through the API.</p>'
        )

        rows = fetch_official_vendor_updates(
            2,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(text=html, url=url),
            registry=registry,
        )
        self.assertGreaterEqual(len(rows), 1)
        titles = "\n".join(row["nameWithOwner"] for row in rows)
        self.assertNotIn("Models & pricing", titles)
        self.assertNotIn("Get API key", titles)
        self.assertTrue(all(row["sourceDetails"]["vendor_record_kind"].startswith("structured_") for row in rows))

    def test_embedded_json_text_can_resolve_mintlify_style_retirement(self):
        registry = (
            {"vendor": "Moonshot AI Kimi", "region": "CN", "release_url": "https://example.com/models", "allowed_domains": ("example.com",)},
        )
        html = (
            '<html><body><div id="app"></div><script>'
            'self.__next_f.push([1,"kimi-k2 系列模型将在 2026 年 5 月 25 日下线，'
            '将不再维护和支持。请使用最新模型 kimi-k2.6。"]);'
            '</script></body></html>'
        )
        rows = fetch_official_vendor_updates(
            2,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(text=html, url=url),
            registry=registry,
        )
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(any(row["sourceDetails"]["vendor_record_kind"] == "structured_embedded" for row in rows))
        self.assertIn("2026", rows[0]["nameWithOwner"])

    def test_fallback_is_explicit_and_not_structured(self):
        registry = (
            {"vendor": "TestVendor", "region": "US", "release_url": "https://example.com/releases", "allowed_domains": ("example.com",)},
        )
        rows = fetch_official_vendor_updates(
            1,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(text="<h1>Documentation</h1><p>Welcome.</p>", url=url),
            registry=registry,
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("page_fallback", rows[0]["sourceDetails"]["vendor_record_kind"])


class Run269InstallTests(unittest.TestCase):
    def test_minimal_pipeline_double_is_noop(self):
        p = SimpleNamespace()
        self.assertIs(p, install(p))
        self.assertFalse(hasattr(p, "_RUN269_BUSINESS_SOURCE_PRECISION_INSTALLED"))

    def test_install_replaces_live_fetch_slots_without_changing_source_architecture(self):
        log = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
        p = SimpleNamespace(
            normalize_item=normalize_item,
            requests=SimpleNamespace(get=lambda *a, **k: FakeResponse(text="", url=a[0])),
            logger=log,
            OFFICIAL_VENDOR_FETCH_LIMIT=20,
            HN_FETCH_LIMIT=20,
            SOURCE_ROI_SOURCES=("GitHub", "HackerNews", "ArXiv", "OfficialVendor"),
        )
        install(p)
        self.assertEqual(("GitHub", "HackerNews", "ArXiv", "OfficialVendor"), p.SOURCE_ROI_SOURCES)
        self.assertTrue(p._RUN269_BUSINESS_SOURCE_PRECISION_INSTALLED)
        self.assertIs(p.fetch_producthunt_trending, p.fetch_official_vendor_updates)
        self.assertEqual(11, len(p.OFFICIAL_VENDOR_REGISTRY))
        self.assertEqual(30, p.HN_LOOKBACK_DAYS)


if __name__ == "__main__":
    unittest.main()
