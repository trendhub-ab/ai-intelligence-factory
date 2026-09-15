from __future__ import annotations

import unittest

from source_stability_layer import (
    RequestsSourceStabilityProxy,
    SourceCircuitOpenError,
)
from x_discovery.providers import ApifyProvider


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", url=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = {}
        self.url = url

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHTTP:
    def __init__(self, *, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if not self.get_responses:
            raise AssertionError("unexpected GET")
        item = self.get_responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        if not self.post_responses:
            raise AssertionError("unexpected POST")
        item = self.post_responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def put(self, *args, **kwargs):
        raise AssertionError("unexpected PUT")

    def patch(self, *args, **kwargs):
        raise AssertionError("unexpected PATCH")


class Run372SourceStabilityTests(unittest.TestCase):
    def test_hn_429_opens_source_circuit_and_prevents_fanout_network_calls(self):
        http = FakeHTTP(get_responses=[FakeResponse(429, text="rate limited")])
        proxy = RequestsSourceStabilityProxy(http, sleep_fn=lambda _seconds: None)

        first = proxy.get("https://hn.algolia.com/api/v1/search", params={"query": "OpenAI"})
        self.assertEqual(first.status_code, 429)
        with self.assertRaises(SourceCircuitOpenError):
            proxy.get("https://hn.algolia.com/api/v1/search", params={"query": "Claude"})
        with self.assertRaises(SourceCircuitOpenError):
            proxy.get("https://hn.algolia.com/api/v1/search", params={"query": "Gemini"})

        self.assertEqual(len(http.get_calls), 1)
        snapshot = proxy.snapshot()
        self.assertEqual(snapshot["circuits_opened"], 1)
        self.assertEqual(snapshot["circuit_skips"], 2)

    def test_official_vendor_success_is_cached_by_exact_request(self):
        response = FakeResponse(200, payload={"ok": True}, text="release notes")
        http = FakeHTTP(get_responses=[response])
        proxy = RequestsSourceStabilityProxy(
            http,
            vendor_hosts={"vendor.example"},
            sleep_fn=lambda _seconds: None,
        )

        one = proxy.get("https://vendor.example/releases", headers={"User-Agent": "one"})
        two = proxy.get("https://vendor.example/releases", headers={"User-Agent": "two"})

        self.assertIs(one, response)
        self.assertIs(two, response)
        self.assertEqual(len(http.get_calls), 1)
        self.assertEqual(proxy.snapshot()["cache_hits"], 1)

    def test_official_vendor_circuit_is_host_scoped_not_global(self):
        http = FakeHTTP(
            get_responses=[
                FakeResponse(503, text="busy"),
                FakeResponse(200, text="healthy"),
            ]
        )
        proxy = RequestsSourceStabilityProxy(
            http,
            vendor_hosts={"a.example", "b.example"},
            sleep_fn=lambda _seconds: None,
        )

        self.assertEqual(proxy.get("https://a.example/releases").status_code, 503)
        with self.assertRaises(SourceCircuitOpenError):
            proxy.get("https://a.example/other")
        self.assertEqual(proxy.get("https://b.example/releases").status_code, 200)
        self.assertEqual(len(http.get_calls), 2)

    def test_github_graphql_errors_without_nodes_cannot_look_like_normal_zero(self):
        payload = {
            "data": {"search": {"nodes": []}},
            "errors": [{"message": "API rate limit exceeded"}],
        }
        http = FakeHTTP(post_responses=[FakeResponse(200, payload=payload, text="graphql error")])
        proxy = RequestsSourceStabilityProxy(http, sleep_fn=lambda _seconds: None)

        response = proxy.post(
            "https://api.github.com/graphql",
            json={"query": "query { search { nodes { id } } }"},
            headers={"Authorization": "Bearer secret"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(proxy.snapshot()["github_graphql_degraded"], 1)
        self.assertEqual(len(http.post_calls), 1)

    def test_github_partial_data_remains_usable_even_when_errors_are_present(self):
        payload = {
            "data": {"search": {"nodes": [{"nameWithOwner": "a/b"}]}},
            "errors": [{"message": "partial warning"}],
        }
        response = FakeResponse(200, payload=payload)
        http = FakeHTTP(post_responses=[response])
        proxy = RequestsSourceStabilityProxy(http, sleep_fn=lambda _seconds: None)

        actual = proxy.post("https://api.github.com/graphql", json={"query": "x"})
        self.assertIs(actual, response)
        self.assertEqual(actual.status_code, 200)

    def test_transient_5xx_get_receives_only_one_bounded_retry(self):
        http = FakeHTTP(get_responses=[FakeResponse(500), FakeResponse(502)])
        proxy = RequestsSourceStabilityProxy(http, sleep_fn=lambda _seconds: None)

        response = proxy.get("https://hn.algolia.com/api/v1/search", params={"query": "LLM"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(http.get_calls), 2)
        with self.assertRaises(SourceCircuitOpenError):
            proxy.get("https://hn.algolia.com/api/v1/search", params={"query": "AI agent"})
        self.assertEqual(len(http.get_calls), 2)


class Run372ApifyCircuitTests(unittest.TestCase):
    @staticmethod
    def _provider(handles):
        return ApifyProvider(
            token="token",
            actor_id="simple.actor~x-profile-posts",
            actor_input={
                "handles": list(handles),
                "outputFormat": "profile",
                "isolateProfiles": True,
            },
            max_total_charge_usd=0.05,
        )

    def test_provider_wide_503_stops_remaining_isolated_profiles(self):
        provider = self._provider(["a", "b", "c", "d"])
        calls = []

        def fake_request(actor_input, *, paid_item_cap, charge_cap_usd):
            calls.append(actor_input["handles"][0])
            raise RuntimeError("Apify HTTP 503: Service Unavailable")

        provider._request = fake_request
        rows = provider.fetch(max_records=10)

        self.assertEqual(rows, [])
        self.assertEqual(calls, ["a"])
        circuit = [row for row in provider.provider_errors if row.get("error") == "provider_circuit_open"]
        self.assertEqual(len(circuit), 1)
        self.assertEqual(circuit[0]["remaining_profiles_skipped"], "3")

    def test_profile_specific_failure_does_not_poison_other_profiles(self):
        provider = self._provider(["a", "b", "c"])
        calls = []

        def fake_request(actor_input, *, paid_item_cap, charge_cap_usd):
            handle = actor_input["handles"][0]
            calls.append(handle)
            if handle == "a":
                raise RuntimeError("profile unavailable")
            return [{"handle": handle, "posts": []}]

        provider._request = fake_request
        provider.fetch(max_records=10)

        self.assertEqual(calls, ["a", "b", "c"])
        self.assertFalse(any(row.get("error") == "provider_circuit_open" for row in provider.provider_errors))


if __name__ == "__main__":
    unittest.main()
