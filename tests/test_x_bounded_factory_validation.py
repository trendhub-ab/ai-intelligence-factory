import unittest

from x_discovery.bounded_factory_validation import (
    BoundedValidationError,
    run_bounded_validation,
    validate_saved_candidate,
)


class FakePipeline:
    def __init__(self, existing=None):
        self._existing = set() if existing is None else existing
        self.alerts = []
        self.prompt_calls = 0
        self.provider_calls = 0
        self.write_calls = 0

    def send_telegram_alert(self, message):
        self.alerts.append(message)

    def get_existing_repo_urls(self):
        return self._existing

    def _batch_screening_prompt(self, batch):
        self.prompt_calls += 1
        assert len(batch) == 1
        assert batch[0]["screening_id"] == "X0001"
        assert batch[0]["repo"]["stargazerCount"] == 0
        return "screen exactly one saved candidate"

    def call_screening_provider(self, *_args, **_kwargs):
        self.provider_calls += 1
        raise AssertionError("model/provider must never be called")

    def persist_to_notion(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("Factory writes must never be called")


def payload(url="https://example.com/defense-factory"):
    return {
        "schema_version": 1,
        "lane": "x_saved_candidate_validation",
        "factory_write": False,
        "evidence_promoted": False,
        "candidate": {
            "canonical_url": url,
            "x_post_id": "2097786616311840853",
            "x_post_url": "https://x.com/example/status/2097786616311840853",
            "author": "example",
            "source_platform": "x",
            "source_role": "discovery_signal",
            "evidence_status": "discovery_only",
            "is_evidence": False,
            "factory_write": False,
        },
        "prepared_primary_source": {
            "url": url,
            "title": "Defense Factory",
            "text": "A" * 500,
        },
    }


class BoundedFactoryValidationTests(unittest.TestCase):
    def test_reaches_prompt_boundary_without_provider_or_write(self):
        fake = FakePipeline()
        result = run_bounded_validation(fake, payload())
        self.assertEqual(result["status"], "SCREENING_BOUNDARY_READY")
        self.assertEqual(result["candidate_count"], 1)
        self.assertTrue(result["dedup_verified"])
        self.assertFalse(result["screening_executed"])
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["source_fetch_calls"], 0)
        self.assertFalse(result["factory_write"])
        self.assertEqual(fake.prompt_calls, 1)
        self.assertEqual(fake.provider_calls, 0)
        self.assertEqual(fake.write_calls, 0)
        self.assertEqual(fake.alerts, [])

    def test_duplicate_is_fail_closed(self):
        fake = FakePipeline(existing={"https://example.com/defense-factory"})
        with self.assertRaisesRegex(BoundedValidationError, "already exists"):
            run_bounded_validation(fake, payload())
        self.assertEqual(fake.prompt_calls, 0)
        self.assertEqual(fake.provider_calls, 0)

    def test_dedup_read_failure_is_fail_closed_and_alert_suppressed(self):
        fake = FakePipeline(existing=None)
        fake._existing = None
        with self.assertRaisesRegex(BoundedValidationError, "deduplication could not be verified"):
            run_bounded_validation(fake, payload())
        self.assertEqual(fake.prompt_calls, 0)
        self.assertEqual(fake.alerts, [])

    def test_rejects_evidence_promotion(self):
        bad = payload()
        bad["candidate"]["is_evidence"] = True
        with self.assertRaisesRegex(BoundedValidationError, "is_evidence must be false"):
            validate_saved_candidate(bad)

    def test_rejects_primary_source_url_mismatch(self):
        bad = payload()
        bad["prepared_primary_source"]["url"] = "https://example.com/other"
        with self.assertRaisesRegex(BoundedValidationError, "must match"):
            validate_saved_candidate(bad)

    def test_rejects_short_saved_body(self):
        bad = payload()
        bad["prepared_primary_source"]["text"] = "too short"
        with self.assertRaisesRegex(BoundedValidationError, "too short"):
            validate_saved_candidate(bad)


if __name__ == "__main__":
    unittest.main()
