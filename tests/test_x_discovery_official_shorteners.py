import unittest
from unittest.mock import patch

from x_discovery.url_resolution import (
    OfficialShortenerResolver,
    enrich_record_with_shorteners,
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
        return FakeResponse(self.__class__.locations.get((self.host, self.path)))

    def close(self):
        pass


class OfficialShortenerTests(unittest.TestCase):
    def setUp(self):
        FakeConnection.locations = {}
        FakeConnection.requested = []

    def test_msft_chain_can_continue_through_aka_ms_but_never_fetch_destination(self):
        FakeConnection.locations[("msft.it", "/abc")] = "http://aka.ms/research"
        FakeConnection.locations[("aka.ms", "/research")] = "https://www.microsoft.com/en-us/research/blog/example?ocid=x"
        resolver = OfficialShortenerResolver()
        with patch("x_discovery.url_resolution.http.client.HTTPSConnection", FakeConnection):
            resolved = resolver.resolve("https://msft.it/abc")

        self.assertEqual(resolved, "https://www.microsoft.com/en-us/research/blog/example")
        self.assertEqual(resolver.calls, 1)
        self.assertEqual(resolver.successes, 1)
        self.assertEqual(resolver.failures, 0)
        self.assertEqual(resolver.unresolved_chains, 0)
        self.assertEqual([host for host, _, _ in FakeConnection.requested], ["msft.it", "aka.ms"])
        self.assertNotIn("www.microsoft.com", [host for host, _, _ in FakeConnection.requested])

    def test_nvda_first_hop_resolves_and_tracking_is_removed(self):
        FakeConnection.locations[("nvda.ws", "/ticket")] = "https://developer.nvidia.com/gtc?ncid=so-twit-1"
        resolver = OfficialShortenerResolver()
        with patch("x_discovery.url_resolution.http.client.HTTPSConnection", FakeConnection):
            resolved = resolver.resolve("https://nvda.ws/ticket")
        self.assertEqual(resolved, "https://developer.nvidia.com/gtc")
        self.assertEqual(resolver.successes, 1)

    def test_unresolved_official_shortener_is_filtered_fail_closed(self):
        record = {"id": "1", "text": "read https://msft.it/missing", "urls": ["https://msft.it/missing"]}
        resolver = OfficialShortenerResolver()
        with patch("x_discovery.url_resolution.http.client.HTTPSConnection", FakeConnection):
            enriched = enrich_record_with_shorteners(record, [resolver])
        self.assertEqual(extract_external_urls(enriched, enriched["text"]), [])
        self.assertEqual(resolver.failures, 1)

    def test_arbitrary_shortener_is_never_connected(self):
        resolver = OfficialShortenerResolver()
        with patch("x_discovery.url_resolution.http.client.HTTPSConnection", FakeConnection):
            self.assertIsNone(resolver.resolve("https://bit.ly/example"))
        self.assertEqual(FakeConnection.requested, [])
        self.assertEqual(resolver.calls, 0)


if __name__ == "__main__":
    unittest.main()
