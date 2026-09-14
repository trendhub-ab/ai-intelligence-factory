import unittest

from x_discovery.dedupe import cluster_candidates
from x_discovery.normalize import normalize_post
from x_discovery.url_resolution import is_primary_source_candidate


class XDiscoveryCandidateQualityTests(unittest.TestCase):
    def test_http_https_variants_cluster_to_one_candidate_and_prefer_https(self):
        a = normalize_post(
            {"id": "a", "username": "one", "text": "http://mistral.ai/news/test"},
            provider="fixture",
            discovered_at="t",
        )
        b = normalize_post(
            {"id": "b", "username": "two", "text": "https://mistral.ai/news/test"},
            provider="fixture",
            discovered_at="t",
        )
        candidates = cluster_candidates([a, b])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].canonical_url, "https://mistral.ai/news/test")
        self.assertEqual(candidates[0].mention_count, 2)
        self.assertEqual(set(candidates[0].authors), {"one", "two"})

    def test_current_official_ai_domains_are_primary_source_candidates(self):
        urls = [
            "https://mistral.ai/news/example",
            "https://blogs.nvidia.com/blog/example",
            "https://docs.langchain.com/example",
            "https://www.llamaindex.ai/blog/example",
            "https://www.perplexity.ai/hub/blog/example",
            "https://replicate.com/example/model",
            "https://x.ai/news/example",
            "https://cohere.com/newsroom/example",
            "https://chatgpt.com/plugins/example",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(is_primary_source_candidate(url))

    def test_event_and_generic_video_hosts_are_not_primary_by_domain_alone(self):
        for url in ("https://luma.com/event", "https://muse.ai/video"):
            with self.subTest(url=url):
                self.assertFalse(is_primary_source_candidate(url))


if __name__ == "__main__":
    unittest.main()
