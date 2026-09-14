import json
import tempfile
import unittest
from pathlib import Path

from x_discovery.handoff import build_primary_resolution_queue
from x_discovery.models import DiscoveryCandidate
from x_discovery.providers import FixtureProvider
from x_discovery.runner import run_ingestion


FIXTURE = Path(__file__).resolve().parents[1] / "x_discovery" / "fixtures" / "sample_posts.json"


class XDiscoveryHandoffTests(unittest.TestCase):
    def test_queue_contains_only_primary_candidates_and_never_promotes_evidence(self):
        queue = build_primary_resolution_queue(
            [
                DiscoveryCandidate(
                    canonical_url="https://www.anthropic.com/research/test",
                    mention_count=2,
                    authors=["a", "b"],
                    post_ids=["1", "2"],
                    post_urls=["https://x.com/a/status/1", "https://x.com/b/status/2"],
                    primary_source_candidate=True,
                ),
                DiscoveryCandidate(
                    canonical_url="https://luma.com/event",
                    mention_count=3,
                    primary_source_candidate=False,
                ),
                DiscoveryCandidate(
                    canonical_url="https://msft.it/short",
                    mention_count=1,
                    primary_source_candidate=True,
                ),
            ]
        )
        self.assertEqual(queue["item_count"], 1)
        self.assertFalse(queue["factory_write"])
        self.assertFalse(queue["evidence_promoted"])
        item = queue["items"][0]
        self.assertEqual(item["canonical_url"], "https://www.anthropic.com/research/test")
        self.assertEqual(item["source_role"], "discovery_signal")
        self.assertEqual(item["resolution_status"], "candidate_needs_primary_verification")
        self.assertFalse(item["is_evidence"])
        self.assertFalse(item["factory_write"])

    def test_runner_always_writes_inert_resolution_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = run_ingestion(
                FixtureProvider(FIXTURE),
                output_dir=root,
                max_records=20,
                discovered_at="2026-09-10T00:00:00+00:00",
            )
            queue_path = root / "primary_resolution_queue.json"
            self.assertTrue(queue_path.exists())
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["primary_resolution_queue_count"], queue["item_count"])
            self.assertFalse(queue["factory_write"])
            self.assertFalse(queue["evidence_promoted"])
            for item in queue["items"]:
                self.assertFalse(item["is_evidence"])
                self.assertFalse(item["factory_write"])
                self.assertNotIn("x.com/", item["canonical_url"])


if __name__ == "__main__":
    unittest.main()
