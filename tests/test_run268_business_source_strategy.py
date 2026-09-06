from __future__ import annotations

from types import SimpleNamespace
import unittest

from business_source_acquisition import (
    HN_AI_QUERIES,
    HN_ALGOLIA_ENDPOINT,
    HN_LOOKBACK_DAYS,
    OFFICIAL_VENDOR_REGISTRY,
    SOURCE_ROLE_CONTRACT,
    fetch_hackernews_ai_reactions,
    fetch_official_vendor_updates,
)
from run268_business_source_strategy import ACTIVE_SOURCE_ORDER, install
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


class Run268AcquisitionTests(unittest.TestCase):
    def test_source_roles_are_exact_four_source_contract(self):
        self.assertEqual(
            SOURCE_ROLE_CONTRACT,
            {
                "GitHub": "implementation_momentum",
                "ArXiv": "frontier_research",
                "HackerNews": "market_engineer_reaction",
                "OfficialVendor": "commercial_primary_source",
            },
        )
        self.assertEqual(ACTIVE_SOURCE_ORDER, ("GitHub", "HackerNews", "ArXiv", "OfficialVendor"))
        self.assertNotIn("ProductHunt", ACTIVE_SOURCE_ORDER)

    def test_registry_contains_western_three_and_chinese_eight(self):
        names = {row["vendor"] for row in OFFICIAL_VENDOR_REGISTRY}
        required = {
            "OpenAI", "Anthropic", "Google Gemini",
            "Alibaba Qwen", "DeepSeek", "ByteDance Doubao/Seed", "Moonshot AI Kimi",
            "Zhipu AI GLM", "MiniMax", "Baidu ERNIE", "Tencent Hunyuan",
        }
        self.assertEqual(required, names)
        regions = {row["vendor"]: row["region"] for row in OFFICIAL_VENDOR_REGISTRY}
        self.assertEqual(3, sum(1 for region in regions.values() if region == "US"))
        self.assertEqual(8, sum(1 for region in regions.values() if region == "CN"))

    def test_official_vendor_fetch_keeps_vendor_metadata_and_round_robin(self):
        registry = (
            {"vendor": "OpenAI", "region": "US", "release_url": "https://openai.com/releases", "allowed_domains": ("openai.com",)},
            {"vendor": "DeepSeek", "region": "CN", "release_url": "https://deepseek.com/releases", "allowed_domains": ("deepseek.com",)},
        )
        pages = {
            "https://openai.com/releases": '<nav><a href="/pricing">Models & pricing</a></nav><h1>Release notes</h1><h2>September 7, 2026</h2><a href="/release/one">API pricing update</a><a href="/release/two">SDK update released</a>',
            "https://deepseek.com/releases": '<nav><a href="/docs">DeepSeek API Docs</a></nav><h1>Change Log</h1><h2>2026-09-07</h2><a href="/release/a">API 价格更新</a><a href="/release/b">模型接口升级</a>',
        }

        def fake_get(url, **kwargs):
            return FakeResponse(text=pages[url], url=url)

        rows = fetch_official_vendor_updates(
            4,
            normalize_item=normalize_item,
            http_get=fake_get,
            registry=registry,
        )
        self.assertEqual(4, len(rows))
        self.assertEqual(["OpenAI", "DeepSeek", "OpenAI", "DeepSeek"], [r["sourceDetails"]["vendor"] for r in rows])
        for row in rows:
            self.assertEqual("OfficialVendor", row["source"])
            self.assertIn(row["sourceDetails"]["vendor_region"], {"US", "CN"})
            self.assertEqual("commercial_primary_source", row["sourceDetails"]["source_role"])
            self.assertEqual("structured", row["sourceDetails"]["vendor_record_kind"])
            self.assertTrue(row["primaryUrl"].startswith("https://"))
            self.assertNotIn("Models & pricing", row["nameWithOwner"])
            self.assertNotIn("DeepSeek API Docs", row["nameWithOwner"])

    def test_vendor_navigation_before_h1_is_never_promoted_to_update(self):
        registry = (
            {"vendor": "Anthropic", "region": "US", "release_url": "https://example.com/releases", "allowed_domains": ("example.com",)},
        )
        html = (
            '<a href="/models">Models & pricing</a><a href="/key">Get API key</a>'
            '<h1>Release notes</h1><h3>August 7, 2026</h3>'
            '<li>You can now set a model inference budget for managed agent sessions.</li>'
        )

        def fake_get(url, **kwargs):
            return FakeResponse(text=html, url=url)

        row = fetch_official_vendor_updates(1, normalize_item=normalize_item, http_get=fake_get, registry=registry)[0]
        self.assertIn("inference budget", row["nameWithOwner"])
        self.assertEqual("structured", row["sourceDetails"]["vendor_record_kind"])
        self.assertNotIn("Models & pricing", row["nameWithOwner"])
        self.assertNotIn("Get API key", row["nameWithOwner"])

    def test_vendor_fallback_is_explicit_and_cannot_masquerade_as_structured(self):
        registry = (
            {"vendor": "OpenAI", "region": "US", "release_url": "https://openai.com/releases", "allowed_domains": ("openai.com",)},
        )

        def fake_get(url, **kwargs):
            return FakeResponse(text="<h1>Release notes</h1><p>Documentation landing page.</p>", url=url)

        row = fetch_official_vendor_updates(1, normalize_item=normalize_item, http_get=fake_get, registry=registry)[0]
        self.assertEqual("page_fallback", row["sourceDetails"]["vendor_record_kind"])
        self.assertIn("structured update not resolved", row["nameWithOwner"])

    def test_vendor_page_level_candidate_gets_revision_identity_but_primary_url_stays_official(self):
        registry = (
            {"vendor": "OpenAI", "region": "US", "release_url": "https://openai.com/releases", "allowed_domains": ("openai.com",)},
        )

        def fake_get(url, **kwargs):
            return FakeResponse(text="<h2>2026-09-07 model API release update</h2>", url=url)

        row = fetch_official_vendor_updates(1, normalize_item=normalize_item, http_get=fake_get, registry=registry)[0]
        self.assertEqual("https://openai.com/releases", row["primaryUrl"])
        self.assertIn("aif_revision=", row["url"])
        self.assertEqual("structured", row["sourceDetails"]["vendor_record_kind"])

    def test_hn_default_queries_are_high_precision_and_no_raw_ai_query(self):
        self.assertNotIn("AI", HN_AI_QUERIES)
        self.assertIn("DeepSeek", HN_AI_QUERIES)
        self.assertIn("Qwen", HN_AI_QUERIES)
        self.assertEqual(30, HN_LOOKBACK_DAYS)

    def test_hn_algolia_is_title_scoped_fresh_bounded_and_deduped(self):
        calls = []

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            query = kwargs["params"]["query"]
            return FakeResponse(
                payload={
                    "hits": [
                        {"objectID": "42", "title": "LLM and DeepSeek ecosystem update", "url": "https://example.com/ai", "points": 90, "num_comments": 20, "created_at_i": 1788700000},
                        {"objectID": "43" + query, "title": f"{query} developer discussion", "url": "", "points": 10, "num_comments": 3, "created_at_i": 1788700001},
                    ]
                },
                url=url,
            )

        rows = fetch_hackernews_ai_reactions(
            5,
            normalize_item=normalize_item,
            http_get=fake_get,
            queries=("LLM", "DeepSeek"),
        )
        self.assertLessEqual(len(rows), 5)
        self.assertEqual(2, len(calls))
        self.assertTrue(all(call[0] == HN_ALGOLIA_ENDPOINT for call in calls))
        self.assertTrue(all(call[1]["params"]["tags"] == "story" for call in calls))
        self.assertTrue(all(call[1]["params"]["restrictSearchableAttributes"] == "title" for call in calls))
        self.assertTrue(all(call[1]["params"]["numericFilters"].startswith("created_at_i>") for call in calls))
        self.assertEqual(1, sum(1 for row in rows if row["sourceDetails"]["hn_id"] == "42"))
        self.assertTrue(all(row["source"] == "HackerNews" for row in rows))
        self.assertTrue(all(row["sourceDetails"]["matched_query"] in {"LLM", "DeepSeek"} for row in rows))
        self.assertTrue(all(row["sourceDetails"]["lookback_days"] == 30 for row in rows))


class Run268InstallTests(unittest.TestCase):
    def _fake_pipeline(self):
        log = SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
        p = SimpleNamespace(
            PRODUCTHUNT_FETCH_LIMIT=50,
            GITHUB_FETCH_LIMIT=50,
            HN_FETCH_LIMIT=50,
            ARXIV_FETCH_LIMIT=50,
            SOURCE_ROI_MAX_FETCH_MULTIPLIER=2,
            SOURCE_ROI_SOURCES=("GitHub", "HackerNews", "ArXiv", "ProductHunt"),
            SOURCE_ROI_MAX_FETCH_BY_SOURCE={},
            ENGAGEMENT_LABELS={"GitHub": "Stars", "HackerNews": "HN_Points", "ArXiv": "N/A", "ProductHunt": "Votes"},
            PRODUCTHUNT_DEVELOPER_TOKEN=None,
            initialize_runtime=lambda: None,
            normalize_item=normalize_item,
            requests=SimpleNamespace(get=lambda *a, **k: FakeResponse(text="", url=a[0])),
            logger=log,
        )

        def rr(groups, limit):
            out = []
            for values in groups.values():
                out.extend(values)
            return out[:limit]

        p.round_robin_candidates = rr
        p.allocate_source_fetch_limits = lambda *a, **k: {
            "GitHub": 40, "HackerNews": 40, "ArXiv": 40, "OfficialVendor": 30
        }
        return p

    def test_install_retires_producthunt_from_active_contract_but_keeps_internal_alias(self):
        p = install(self._fake_pipeline())
        self.assertEqual(ACTIVE_SOURCE_ORDER, p.SOURCE_ROI_SOURCES)
        self.assertNotIn("ProductHunt", p._source_base_fetch_limits())
        limits = p.allocate_source_fetch_limits()
        self.assertEqual(limits["OfficialVendor"], limits["ProductHunt"])
        self.assertEqual("N/A (official primary source)", p.ENGAGEMENT_LABELS["OfficialVendor"])

    def test_round_robin_mutates_legacy_slot_to_officialvendor_before_screening(self):
        p = install(self._fake_pipeline())
        groups = {
            "GitHub": [],
            "HackerNews": [],
            "ArXiv": [],
            "ProductHunt": [{"source": "OfficialVendor", "sourceDetails": {"vendor": "DeepSeek"}}],
        }
        rows = p.round_robin_candidates(groups, 5)
        self.assertNotIn("ProductHunt", groups)
        self.assertIn("OfficialVendor", groups)
        self.assertEqual("OfficialVendor", rows[0]["source"])
        self.assertEqual("commercial_primary_source", rows[0]["sourceDetails"]["source_role"])

    def test_initialize_runtime_does_not_require_producthunt_token_after_install(self):
        seen = []
        p = self._fake_pipeline()

        def legacy_initialize():
            seen.append(p.PRODUCTHUNT_DEVELOPER_TOKEN)
            if not p.PRODUCTHUNT_DEVELOPER_TOKEN:
                raise ValueError("legacy Product Hunt token required")

        p.initialize_runtime = legacy_initialize
        install(p)
        p.initialize_runtime()
        self.assertEqual(["RUN268_OFFICIAL_VENDOR_NO_TOKEN_REQUIRED"], seen)
        self.assertIsNone(p.PRODUCTHUNT_DEVELOPER_TOKEN)


if __name__ == "__main__":
    unittest.main()
