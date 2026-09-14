import unittest
from unittest.mock import patch

from x_discovery.url_resolution import (
    TcoRedirectResolver,
    enrich_record_with_tco,
    extract_external_urls,
)


class FakeResponse:
    def __init__(self, location):
        self.location = location

    def getheader(self, name):
        return self.location if name.lower() == "location" else None

    def read(self, amount=-1):
        return b""


class FakeConnection:
    locations = {}
    requested = []

    def __init__(self, host, timeout):
        self.host = host
        self.timeout = timeout
        self.path = None

    def request(self, method, path, headers=None):
        self.path = path
        self.__class__.requested.append((self.host, method, path))

    def getresponse(self):
        return FakeResponse(self.__class__.locations.get(self.path))

    def close(self):
        pass


class TcoResolutionTests(unittest.TestCase):
    def setUp(self):
        FakeConnection.locations = {}
        FakeConnection.requested = []

    def test_resolves_only_first_tco_redirect_and_strips_tracking(self):
        FakeConnection.locations["/abc"] = "https://Example.com/release?utm_source=x&a=1"
        resolver = TcoRedirectResolver()
        with patch("x_discovery.url_resolution.http.client.HTTPSConnection", FakeConnection):
            resolved = resolver.resolve("https://t.co/abc")
            again = resolver.resolve("https://t.co/abc")

        self.assertEqual(resolved, "https://example.com/release?a=1")
        self.assertEqual(again, resolved)
        self.assertEqual(resolver.calls, 1)
        self.assertEqual(resolver.successes, 1)
        self.assertEqual(resolver.internal_resolutions, 0)
        self.assertEqual(resolver.failures, 0)
        self.assertTrue(FakeConnection.requested)
        self.assertTrue(all(host == "t.co" for host, _, _ in FakeConnection.requested))

    def test_classifies_redirect_back_to_x_as_internal_not_failure(self):
        FakeConnection.locations["/internal"] = "https://x.com/i/article/123"
        resolver = TcoRedirectResolver()
        with patch("x_discovery.url_resolution.http.client.HTTPSConnection", FakeConnection):
            self.assertIsNone(resolver.resolve("https://t.co/internal"))
        self.assertEqual(resolver.successes, 0)
        self.assertEqual(resolver.internal_resolutions, 1)
        self.assertEqual(resolver.failures, 0)

    def test_counts_missing_redirect_as_failure(self):
        resolver = TcoRedirectResolver()
        with patch("x_discovery.url_resolution.http.client.HTTPSConnection", FakeConnection):
            self.assertIsNone(resolver.resolve("https://t.co/missing"))
        self.assertEqual(resolver.internal_resolutions, 0)
        self.assertEqual(resolver.failures, 1)

    def test_enrichment_turns_tco_into_external_candidate_without_fetching_destination(self):
        FakeConnection.locations["/source"] = "https://arxiv.org/abs/2609.12345?utm_campaign=x"
        resolver = TcoRedirectResolver()
        record = {"id": "1", "text": "paper https://t.co/source", "urls": []}
        with patch("x_discovery.url_resolution.http.client.HTTPSConnection", FakeConnection):
            enriched = enrich_record_with_tco(record, resolver)

        self.assertEqual(enriched["urls"], ["https://arxiv.org/abs/2609.12345"])
        self.assertEqual(
            extract_external_urls(enriched, enriched["text"]),
            ["https://arxiv.org/abs/2609.12345"],
        )
        self.assertEqual(resolver.calls, 1)


if __name__ == "__main__":
    unittest.main()
