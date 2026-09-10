import copy
import json
import tempfile
import unittest
from pathlib import Path

from x_discovery.factory_adapter import (
    FactoryAdapterContractError,
    adapt_primary_resolution_queue,
    main,
)


def _valid_item(url: str = "https://www.anthropic.com/research/test"):
    return {
        "canonical_url": url,
        "mention_count": 2,
        "authors": ["researcher_a", "engineer_b"],
        "x_post_ids": ["1", "2"],
        "x_post_urls": [
            "https://x.com/researcher_a/status/1",
            "https://twitter.com/engineer_b/status/2",
        ],
        "source_platform": "x",
        "source_role": "discovery_signal",
        "resolution_status": "candidate_needs_primary_verification",
        "evidence_status": "discovery_only",
        "is_evidence": False,
        "factory_write": False,
    }


def _valid_queue(items=None):
    values = list(items if items is not None else [_valid_item()])
    return {
        "schema_version": 1,
        "queue_type": "x_primary_source_resolution",
        "source_platform": "x",
        "evidence_status": "discovery_only",
        "factory_write": False,
        "evidence_promoted": False,
        "item_count": len(values),
        "items": values,
    }


class XDiscoveryFactoryAdapterTests(unittest.TestCase):
    def test_accepts_primary_candidate_and_forces_inert_controls(self):
        queue = _valid_queue()
        original = copy.deepcopy(queue)

        preview = adapt_primary_resolution_queue(queue)

        self.assertEqual(queue, original)
        self.assertEqual(preview["accepted_count"], 1)
        self.assertEqual(preview["rejected_count"], 0)
        self.assertFalse(preview["factory_write"])
        self.assertFalse(preview["screening_executed"])
        self.assertFalse(preview["evidence_promoted"])
        item = preview["items"][0]
        self.assertFalse(item["factory_write"])
        self.assertFalse(item["is_evidence"])
        self.assertFalse(item["screening_executed"])
        self.assertFalse(item["evidence_promoted"])

    def test_canonicalizes_and_deduplicates_primary_urls(self):
        first = _valid_item(
            "https://github.com/example/project/?utm_source=x&b=2&a=1"
        )
        second = _valid_item(
            "https://github.com/example/project?a=1&b=2&utm_campaign=again"
        )
        queue = _valid_queue([first, second])

        preview = adapt_primary_resolution_queue(queue)

        self.assertEqual(preview["accepted_count"], 1)
        self.assertEqual(preview["rejected_count"], 1)
        self.assertEqual(
            preview["items"][0]["canonical_url"],
            "https://github.com/example/project?a=1&b=2",
        )
        self.assertEqual(
            preview["rejections"][0]["reason"],
            "duplicate_primary_url",
        )

    def test_rejects_unsafe_or_unqualified_items_fail_closed(self):
        cases = []

        x_target = _valid_item("https://x.com/openai/status/1")
        cases.append(("x_target_url", x_target))

        short_target = _valid_item("https://t.co/abc")
        cases.append(("unresolved_short_url", short_target))

        non_primary = _valid_item("https://example.com/article")
        cases.append(("non_primary_source_candidate", non_primary))

        bad_provenance = _valid_item()
        bad_provenance["x_post_urls"] = ["https://example.com/not-x"]
        cases.append(("invalid_x_post_urls", bad_provenance))

        evidence_attempt = _valid_item()
        evidence_attempt["is_evidence"] = True
        cases.append(("evidence_promotion_attempt", evidence_attempt))

        write_attempt = _valid_item()
        write_attempt["factory_write"] = True
        cases.append(("factory_write_attempt", write_attempt))

        for expected_reason, item in cases:
            with self.subTest(expected_reason=expected_reason):
                preview = adapt_primary_resolution_queue(_valid_queue([item]))
                self.assertEqual(preview["accepted_count"], 0)
                self.assertEqual(preview["rejected_count"], 1)
                self.assertEqual(
                    preview["rejections"][0]["reason"],
                    expected_reason,
                )
                self.assertFalse(preview["factory_write"])
                self.assertFalse(preview["screening_executed"])
                self.assertFalse(preview["evidence_promoted"])

    def test_rejects_invalid_root_contract(self):
        cases = [
            ("factory_write", True),
            ("evidence_promoted", True),
            ("queue_type", "evidence_queue"),
            ("evidence_status", "verified"),
        ]
        for key, value in cases:
            with self.subTest(key=key):
                queue = _valid_queue()
                queue[key] = value
                with self.assertRaises(FactoryAdapterContractError):
                    adapt_primary_resolution_queue(queue)

        queue = _valid_queue()
        queue["item_count"] = 999
        with self.assertRaises(FactoryAdapterContractError):
            adapt_primary_resolution_queue(queue)

    def test_cli_writes_preview_without_factory_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "primary_resolution_queue.json"
            output_path = root / "factory_adapter_preview.json"
            queue_path.write_text(
                json.dumps(_valid_queue(), ensure_ascii=False),
                encoding="utf-8",
            )

            code = main(
                [
                    "--queue",
                    str(queue_path),
                    "--output",
                    str(output_path),
                ]
            )

            self.assertEqual(code, 0)
            preview = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(preview["mode"], "dry_run")
            self.assertFalse(preview["factory_write"])
            self.assertFalse(preview["screening_executed"])
            self.assertFalse(preview["evidence_promoted"])


if __name__ == "__main__":
    unittest.main()
