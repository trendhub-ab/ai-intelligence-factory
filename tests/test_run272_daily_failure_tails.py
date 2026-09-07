import subprocess
import unittest
from unittest import mock

import daily_portfolio_review
import notion_payloads
import product_delivery_maintenance
import source_normalization


class DateNormalizationTests(unittest.TestCase):
    def test_known_vendor_dates_become_iso_dates(self):
        cases = {
            "Sep 3, 2026": "2026-09-03",
            "September 2, 2026": "2026-09-02",
            "2026年8月31日": "2026-08-31",
            "2026/8/31": "2026-08-31",
            "2026.08.31": "2026-08-31",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(source_normalization.canonicalize_published_at(raw), expected)

    def test_valid_iso_is_preserved_and_invalid_fails_closed(self):
        iso = "2026-09-07T02:03:50+00:00"
        self.assertEqual(source_normalization.canonicalize_published_at(iso), iso)
        self.assertIsNone(source_normalization.canonicalize_published_at("September 99, 2026"))
        self.assertEqual(notion_payloads.notion_date_property("September 99, 2026"), {"date": None})

    def test_normalize_item_canonicalizes_before_notion_boundary(self):
        item = source_normalization.normalize_item(
            "OfficialVendor", "Example", "https://example.com", "desc", 0,
            published_at="Sep 3, 2026",
        )
        self.assertEqual(item["publishedAt"], "2026-09-03")


class EvidenceHealthCircuitTests(unittest.TestCase):
    def test_arxiv_fetch_error_opens_run_local_circuit_but_non_arxiv_continues(self):
        states = [
            {"page_id": "a1", "source_type": "arxiv", "url": "https://arxiv.org/abs/1"},
            {"page_id": "a2", "source_type": "arxiv", "url": "https://arxiv.org/abs/2"},
            {"page_id": "g1", "source_type": "github", "url": "https://github.com/o/r"},
        ]
        updates = []
        arxiv_calls = []

        class Ledger:
            ENABLE_EVIDENCE_LEDGER = True

            @staticmethod
            def query_health_candidates(token):
                return states

            @staticmethod
            def check_health(state, fetcher):
                status, text, final = fetcher(state["url"])
                if status < 200 or status >= 400:
                    return {"health": "FETCH_ERROR", "material": False, "final_url": final}
                return {"health": "VERIFIED", "material": False, "final_url": final}

            @staticmethod
            def update_health(page_id, health, token, rereview_triggered=False):
                updates.append((page_id, health["health"], rereview_triggered))

        class Decision:
            NOTION_DECISION_INTELLIGENCE_API_KEY = "token"
            TECH_PROP_NEXT_REVIEW = "Next Review"

            @staticmethod
            def _headers():
                return {}

        result = product_delivery_maintenance.run_evidence_health_maintenance(
            evidence_ledger=Ledger,
            decision_intelligence=Decision,
            requests_module=mock.Mock(),
            logger=mock.Mock(),
            github_repo_name_from_url=lambda url: "o/r",
            fetch_github_readme_context=lambda repo: "healthy readme",
            extract_arxiv_id=lambda url: url.rsplit("/", 1)[-1],
            fetch_arxiv_api_context=lambda arxiv_id: (arxiv_calls.append(arxiv_id) or "", {}),
            http_get_health_limited=lambda url, limit: (200, "ok", url),
            readable_html_text_parser=mock.Mock,
            web_context_max_bytes=1_500_000,
            now_iso=lambda: "2026-09-07T00:00:00+00:00",
        )

        self.assertEqual(arxiv_calls, ["1"])
        self.assertTrue(result["arxiv_circuit_open"])
        self.assertEqual(result["fetch_errors"], 1)
        self.assertEqual(result["deferred"], 2)
        self.assertEqual(result["checked"], 2)
        self.assertEqual(updates, [("g1", "VERIFIED", False)])


class ProductReviewTimeoutTests(unittest.TestCase):
    def test_timeout_is_deferred_instead_of_killing_daily(self):
        exc = subprocess.TimeoutExpired(
            cmd=["python", "pipeline.py"], timeout=3, output="safe partial output", stderr=""
        )
        with mock.patch.object(daily_portfolio_review.ib, "product_only_environment", return_value={}), \
             mock.patch.object(daily_portfolio_review.ib, "detect_unsafe_pipeline_activity", return_value=[]), \
             mock.patch.object(daily_portfolio_review.subprocess, "run", side_effect=exc):
            result = daily_portfolio_review._run_product_only(["entity-1"], 1, 1, timeout=3)
        self.assertTrue(result["timed_out"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "bounded_child_timeout")
        self.assertEqual(result["timeout_seconds"], 3)

    def test_timeout_partial_output_still_runs_safety_detector(self):
        exc = subprocess.TimeoutExpired(
            cmd=["python", "pipeline.py"], timeout=3, output="unsafe marker", stderr=""
        )
        with mock.patch.object(daily_portfolio_review.ib, "product_only_environment", return_value={}), \
             mock.patch.object(daily_portfolio_review.ib, "detect_unsafe_pipeline_activity", return_value=["unsafe"]), \
             mock.patch.object(daily_portfolio_review.subprocess, "run", side_effect=exc):
            with self.assertRaisesRegex(RuntimeError, "safety violation before timeout"):
                daily_portfolio_review._run_product_only(["entity-1"], 1, 1, timeout=3)


if __name__ == "__main__":
    unittest.main()
