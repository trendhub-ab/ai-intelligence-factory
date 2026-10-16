from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import run367_x_daily_discovery as xdaily
from x_discovery.providers import ApifyProvider


class XDiscoveryXquikContractTests(unittest.TestCase):
    def test_run367_uses_xquik_bounded_profile_contract(self):
        handles = xdaily._load_watchlist()
        payload = xdaily.build_actor_input(handles)

        self.assertEqual(xdaily.DEFAULT_ACTOR_ID, "xquik~x-tweet-scraper")
        self.assertEqual(
            payload,
            {
                "twitterHandles": list(handles),
                "mode": "profileTweets",
                "maxItems": 100,
                "maxItemsPerTarget": 5,
                "within_time": "12h",
                "outputVariant": "rich",
                "fieldStyle": "camelCase",
                "outputPreset": "flat",
            },
        )

    def test_apify_provider_counts_xquik_handles_and_sends_one_bounded_run(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    [
                        {
                            "id": "20",
                            "text": "hello",
                            "url": "https://x.com/nasa/status/20",
                            "authorUsername": "nasa",
                        }
                    ]
                ).encode("utf-8")

        provider = ApifyProvider(
            token="secret",
            actor_id="xquik~x-tweet-scraper",
            actor_input={
                "twitterHandles": ["nasa", "OpenAI"],
                "mode": "profileTweets",
                "maxItems": 10,
                "maxItemsPerTarget": 5,
                "within_time": "12h",
                "outputVariant": "rich",
                "fieldStyle": "camelCase",
                "outputPreset": "flat",
            },
            max_total_charge_usd=0.05,
        )

        with patch("x_discovery.providers.urlopen", return_value=FakeResponse()) as mocked:
            items = provider.fetch(max_records=10)

        self.assertEqual(provider.requested_profile_count, 2)
        self.assertEqual(provider.external_calls, 1)
        self.assertEqual(items[0]["id"], "20")
        body = json.loads(mocked.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["twitterHandles"], ["nasa", "OpenAI"])
        self.assertNotIn("handles", body)
        self.assertNotIn("isolateProfiles", body)

    def test_apify_provider_filters_xquik_diagnostic_rows_from_signals(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    [
                        {
                            "id": "diag:zero-output:nasa",
                            "resultType": "diagnostic",
                            "status": "zero-output",
                            "message": "No tweets matched the requested profile window.",
                            "sourceTarget": "nasa",
                        },
                        {
                            "id": "diag:unexpected-error:broken",
                            "resultType": "diagnostic",
                            "status": "unexpected-error",
                            "message": "Actor could not read this target.",
                            "sourceTarget": "broken",
                        },
                        {
                            "id": "21",
                            "text": "fresh",
                            "url": "https://x.com/OpenAI/status/21",
                            "authorUsername": "OpenAI",
                        },
                    ]
                ).encode("utf-8")

        provider = ApifyProvider(
            token="secret",
            actor_id="xquik~x-tweet-scraper",
            actor_input={"twitterHandles": ["nasa", "OpenAI", "broken"], "mode": "profileTweets"},
            max_total_charge_usd=0.05,
        )

        with patch("x_discovery.providers.urlopen", return_value=FakeResponse()):
            items = provider.fetch(max_records=10)

        self.assertEqual([item["id"] for item in items], ["21"])
        self.assertEqual(provider.empty_profile_count, 1)
        self.assertEqual(
            provider.provider_errors,
            [
                {
                    "handle": "broken",
                    "error": "unexpected-error",
                    "description": "Actor could not read this target.",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
