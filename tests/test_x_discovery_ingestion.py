import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from x_discovery.dedupe import cluster_candidates, dedupe_signals
from x_discovery.normalize import normalize_post
from x_discovery.providers import ApifyProvider, FixtureProvider
from x_discovery.runner import run_ingestion
from x_discovery.url_resolution import canonicalize_url, extract_external_urls


FIXTURE = Path(__file__).resolve().parents[1] / "x_discovery" / "fixtures" / "sample_posts.json"


class XDiscoveryIngestionTests(unittest.TestCase):
    def test_canonicalize_strips_tracking_and_fragment(self):
        self.assertEqual(
            canonicalize_url("https://Example.com/a/?utm_source=x&b=2&a=1#part"),
            "https://example.com/a?a=1&b=2",
        )

    def test_extract_external_urls_excludes_internal_and_unresolved_tco(self):
        record = {
            "entities": {"urls": [{"expanded_url": "https://example.org/a?utm_campaign=x"}]},
        }
        text = "https://x.com/u/status/1 https://t.co/abc https://example.org/a"
        self.assertEqual(extract_external_urls(record, text), ["https://example.org/a"])

    def test_normalize_aliases_and_discovery_only_safety(self):
        signal = normalize_post(
            {
                "id_str": "42",
                "author": {"username": "chipwatch"},
                "full_text": "See https://arxiv.org/abs/1234.5678",
                "tweet_url": "https://x.com/chipwatch/status/42",
                "favorite_count": 9,
            },
            provider="fixture",
            discovered_at="2026-09-10T00:00:00+00:00",
        )
        self.assertEqual(signal.post_id, "42")
        self.assertEqual(signal.author_handle, "chipwatch")
        self.assertEqual(signal.engagement_snapshot["likes"], 9)
        self.assertFalse(signal.is_evidence)
        self.assertEqual(signal.evidence_status, "discovery_only")

    def test_simple_actor_schema_normalizes_without_data_loss(self):
        signal = normalize_post(
            {
                "type": "tweet",
                "id": "2090877991228264814",
                "url": "https://x.com/NASA/status/2090877991228264814",
                "text": "New release https://example.org/release",
                "likeCount": 878,
                "replyCount": 65,
                "retweetCount": 138,
                "quoteCount": 6,
                "bookmarkCount": 39,
                "viewCount": 411170,
                "createdAt": "Fri Aug 21 19:05:34 +0000 2026",
                "createdAtIso": "2026-08-21T19:05:34.000Z",
                "urls": ["https://example.org/release?utm_source=x"],
                "author": {"userName": "NASA", "name": "NASA"},
            },
            provider="apify",
            discovered_at="2026-09-10T00:00:00+00:00",
        )
        self.assertEqual(signal.post_id, "2090877991228264814")
        self.assertEqual(signal.author_handle, "NASA")
        self.assertEqual(signal.posted_at, "2026-08-21T19:05:34.000Z")
        self.assertEqual(signal.external_urls, ["https://example.org/release"])
        self.assertEqual(
            signal.engagement_snapshot,
            {
                "likes": 878,
                "reposts": 138,
                "replies": 65,
                "quotes": 6,
                "views": 411170,
                "bookmarks": 39,
            },
        )
        self.assertFalse(signal.is_evidence)

    def test_dedupe_and_cluster_same_url_across_authors(self):
        a = normalize_post(
            {"id": "a", "username": "one", "text": "https://example.com/z?utm_source=x"},
            provider="fixture",
            discovered_at="t",
        )
        b = normalize_post(
            {"id": "b", "username": "two", "text": "https://example.com/z"},
            provider="fixture",
            discovered_at="t",
        )
        duplicate = normalize_post(
            {"id": "a", "username": "one", "text": "https://example.com/z"},
            provider="fixture",
            discovered_at="t",
        )
        fresh, duplicates, _ = dedupe_signals([a, b, duplicate], set())
        self.assertEqual(len(fresh), 2)
        self.assertEqual(duplicates, 1)
        candidates = cluster_candidates(fresh)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].mention_count, 2)
        self.assertEqual(set(candidates[0].authors), {"one", "two"})
        self.assertFalse(candidates[0].is_evidence)

    def test_offline_runner_has_zero_external_calls_and_no_factory_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = run_ingestion(
                FixtureProvider(FIXTURE),
                output_dir=Path(tmp),
                max_records=20,
                discovered_at="2026-09-10T00:00:00+00:00",
            )
            self.assertEqual(manifest["input_count"], 6)
            self.assertEqual(manifest["new_signal_count"], 5)
            self.assertEqual(manifest["duplicate_count"], 1)
            self.assertEqual(manifest["candidate_count"], 3)
            self.assertEqual(manifest["external_provider_calls"], 0)
            self.assertEqual(manifest["provider_error_count"], 0)
            self.assertEqual(manifest["skipped_pinned_count"], 0)
            self.assertEqual(manifest["x_official_api_calls"], 0)
            self.assertFalse(manifest["factory_write"])
            self.assertFalse(manifest["evidence_promoted"])

            candidates = json.loads((Path(tmp) / "discovery_candidates.json").read_text(encoding="utf-8"))
            by_url = {item["canonical_url"]: item for item in candidates}
            self.assertEqual(by_url["https://example.com/post"]["mention_count"], 2)
            self.assertTrue(by_url["https://arxiv.org/abs/2609.01234"]["primary_source_candidate"])
            self.assertTrue(by_url["https://github.com/example/project"]["primary_source_candidate"])
            self.assertTrue((Path(tmp) / "provider_diagnostics.json").exists())

    def test_seen_ids_persist_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seen = root / "seen.json"
            first = run_ingestion(FixtureProvider(FIXTURE), output_dir=root / "one", seen_ids_path=seen)
            second = run_ingestion(FixtureProvider(FIXTURE), output_dir=root / "two", seen_ids_path=seen)
            self.assertEqual(first["new_signal_count"], 5)
            self.assertEqual(second["new_signal_count"], 0)
            self.assertEqual(second["duplicate_count"], 6)

    def test_apify_requires_credentials_and_has_cost_guard(self):
        with self.assertRaises(ValueError):
            ApifyProvider(token="", actor_id="someone~actor")
        with self.assertRaises(ValueError):
            ApifyProvider(token="token", actor_id="someone~actor", max_total_charge_usd=2.0)

    def test_apify_request_uses_bearer_auth_and_budget_caps(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'[{"id":"1","text":"ok"}]'

        provider = ApifyProvider(
            token="secret",
            actor_id="someone~actor",
            actor_input={"handles": ["a"]},
            max_total_charge_usd=0.2,
        )
        with patch("x_discovery.providers.urlopen", return_value=FakeResponse()) as mocked:
            items = provider.fetch(max_records=20)
        self.assertEqual(len(items), 1)
        request = mocked.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer secret")
        self.assertIn("/v2/actors/someone~actor/run-sync-get-dataset-items", request.full_url)
        self.assertIn("maxItems=20", request.full_url)
        self.assertIn("maxTotalChargeUsd=0.2", request.full_url)
        self.assertNotIn("secret", request.full_url)
        self.assertEqual(provider.external_calls, 1)

    def test_apify_skips_pinned_and_provider_error_rows(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    [
                        {"id": "pin", "text": "old pin", "isPinned": True},
                        {"handle": "protected", "error": "profile unavailable"},
                        {"id": "fresh", "text": "new post", "isPinned": False},
                    ]
                ).encode("utf-8")

        provider = ApifyProvider(
            token="secret",
            actor_id="simple.actor~x-profile-posts",
            actor_input={"handles": ["a"]},
            max_total_charge_usd=0.05,
        )
        with patch("x_discovery.providers.urlopen", return_value=FakeResponse()):
            items = provider.fetch(max_records=20)
        self.assertEqual([item["id"] for item in items], ["fresh"])
        self.assertEqual(provider.skipped_pinned, 1)
        self.assertEqual(provider.provider_errors, [{"handle": "protected", "error": "profile unavailable"}])

    def test_apify_profile_mode_flattens_posts_and_preserves_coverage(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    [
                        {
                            "type": "user",
                            "userName": "NASA",
                            "posts": [
                                {"id": "pin", "text": "old", "isPinned": True},
                                {"id": "fresh", "text": "new", "createdAtIso": "2026-09-10T01:00:00Z"},
                            ],
                        },
                        {"type": "user", "userName": "quiet", "posts": []},
                        {
                            "handle": "fast_account",
                            "error": "window_too_wide",
                            "errorDescription": "Five visible posts do not cover the requested window",
                            "oldestVisiblePostAt": "2026-09-10T10:00:00Z",
                        },
                    ]
                ).encode("utf-8")

        provider = ApifyProvider(
            token="secret",
            actor_id="simple.actor~x-profile-posts",
            actor_input={
                "handles": ["NASA", "quiet", "fast_account"],
                "outputFormat": "profile",
                "onlyPostsNewerThan": "12 hours",
            },
            max_total_charge_usd=0.05,
        )
        with patch("x_discovery.providers.urlopen", return_value=FakeResponse()):
            items = provider.fetch(max_records=20)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "fresh")
        self.assertEqual(items[0]["authorUserName"], "NASA")
        self.assertEqual(provider.requested_profile_count, 3)
        self.assertEqual(provider.profile_rows_read, 2)
        self.assertEqual(provider.empty_profile_count, 1)
        self.assertEqual(provider.profiles_with_posts, {"NASA"})
        self.assertEqual(provider.skipped_pinned, 1)
        self.assertEqual(provider.provider_errors[0]["handle"], "fast_account")
        self.assertEqual(provider.provider_errors[0]["error"], "window_too_wide")
        self.assertIn("description", provider.provider_errors[0])
        self.assertEqual(provider.provider_errors[0]["oldest_visible_post_at"], "2026-09-10T10:00:00Z")

    def test_runner_writes_profile_diagnostics_and_provider_raw_items(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    [
                        {
                            "type": "user",
                            "userName": "NASA",
                            "posts": [{"id": "fresh", "text": "https://www.nasa.gov/news", "urls": ["https://www.nasa.gov/news"]}],
                        }
                    ]
                ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            provider = ApifyProvider(
                token="secret",
                actor_id="simple.actor~x-profile-posts",
                actor_input={"handles": ["NASA"], "outputFormat": "profile"},
                max_total_charge_usd=0.05,
            )
            with patch("x_discovery.providers.urlopen", return_value=FakeResponse()):
                manifest = run_ingestion(provider, output_dir=Path(tmp), max_records=20)
            self.assertEqual(manifest["requested_profile_count"], 1)
            self.assertEqual(manifest["profile_rows_read"], 1)
            self.assertEqual(manifest["profiles_with_posts_count"], 1)
            self.assertEqual(manifest["empty_profile_count"], 0)
            self.assertTrue((Path(tmp) / "provider_raw_items.json").exists())


if __name__ == "__main__":
    unittest.main()
