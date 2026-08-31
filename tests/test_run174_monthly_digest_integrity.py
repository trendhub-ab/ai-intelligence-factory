import os
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import run174_monthly_digest_integrity as run174


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def pages_for(total_returned, *, final_status="complete", final_reason="", server_incomplete=False):
    pages = []
    remaining = total_returned
    cursor = 0
    while remaining > 0:
        take = min(100, remaining)
        remaining -= take
        is_last = remaining == 0
        body = {
            "results": [{"id": cursor + i} for i in range(take)],
            "has_more": not is_last,
            "next_cursor": str(cursor + take) if not is_last else None,
        }
        if is_last:
            if server_incomplete:
                body["request_status"] = {
                    "type": "incomplete",
                    "incomplete_reason": final_reason or "query_result_limit_reached",
                }
            elif final_status:
                body["request_status"] = {"type": final_status}
                if final_reason:
                    body["request_status"]["incomplete_reason"] = final_reason
        pages.append(FakeResponse(body))
        cursor += take
    if not pages:
        pages.append(FakeResponse({"results": [], "has_more": False, "request_status": {"type": final_status}}))
    return pages


def fake_pipeline(responses=None, fetch_override=None):
    ns = types.SimpleNamespace()
    ns.logger = MagicMock()
    ns.MONTHLY_DIGEST_MAX_ITEMS = 500
    queue = list(responses or [])

    def query(url, headers, payload):
        return queue.pop(0) if queue else None

    ns._query_notion_db_with_retry = query

    def legacy_fetch(start, end):
        items = []
        while True:
            response = ns._query_notion_db_with_retry("notion", {}, {"page_size": 100})
            if response is None:
                return None
            body = response.json()
            items.extend(body.get("results", []))
            if body.get("has_more") and len(items) < ns.MONTHLY_DIGEST_MAX_ITEMS:
                continue
            break
        return items

    ns.fetch_monthly_dataset = fetch_override or legacy_fetch
    return ns


class Run174MonthlyDigestIntegrityTests(unittest.TestCase):
    def test_501_rows_are_not_silently_cut_at_legacy_500(self):
        p = fake_pipeline(pages_for(501))
        run174.install(p)
        rows = p.fetch_monthly_dataset("start", "end")
        self.assertEqual(501, len(rows))
        self.assertEqual(500, p.MONTHLY_DIGEST_MAX_ITEMS)

    def test_750_rows_complete_pass(self):
        p = fake_pipeline(pages_for(750))
        run174.install(p)
        self.assertEqual(750, len(p.fetch_monthly_dataset("start", "end")))

    def test_exact_10000_with_explicit_complete_status_passes(self):
        p = fake_pipeline(pages_for(10_000))
        run174.install(p)
        rows = p.fetch_monthly_dataset("start", "end")
        self.assertEqual(10_000, len(rows))

    def test_server_truncated_over_10000_is_refused_even_when_only_10000_are_returned(self):
        p = fake_pipeline(pages_for(10_000, server_incomplete=True))
        run174.install(p)
        self.assertIsNone(p.fetch_monthly_dataset("start", "end"))
        self.assertTrue(p.logger.error.called)

    def test_incomplete_reason_wins_even_if_status_type_claims_complete(self):
        p = fake_pipeline(pages_for(10_000, final_status="complete", final_reason="query_result_limit_reached"))
        run174.install(p)
        self.assertIsNone(p.fetch_monthly_dataset("start", "end"))

    def test_exact_10000_without_complete_status_is_ambiguous_and_refused(self):
        p = fake_pipeline(pages_for(10_000, final_status=""))
        run174.install(p)
        self.assertIsNone(p.fetch_monthly_dataset("start", "end"))

    def test_lower_local_cap_refuses_when_more_results_exist(self):
        p = fake_pipeline(pages_for(501))
        with patch.dict(os.environ, {"MONTHLY_DIGEST_COMPLETE_MAX_ITEMS": "500"}):
            run174.install(p)
            self.assertIsNone(p.fetch_monthly_dataset("start", "end"))
        self.assertEqual(500, p.MONTHLY_DIGEST_MAX_ITEMS)

    def test_exact_lower_cap_complete_passes(self):
        p = fake_pipeline(pages_for(500))
        with patch.dict(os.environ, {"MONTHLY_DIGEST_COMPLETE_MAX_ITEMS": "500"}):
            run174.install(p)
            rows = p.fetch_monthly_dataset("start", "end")
        self.assertEqual(500, len(rows))

    def test_underlying_none_remains_none(self):
        p = fake_pipeline([])
        run174.install(p)
        self.assertIsNone(p.fetch_monthly_dataset("start", "end"))

    def test_wrapped_helper_and_legacy_limit_restore_after_exception(self):
        p = fake_pipeline([])
        original_query = p._query_notion_db_with_retry

        def boom(start, end):
            # Prove the temporary complete cap is active inside the wrapped call.
            self.assertEqual(10_000, p.MONTHLY_DIGEST_MAX_ITEMS)
            raise RuntimeError("boom")

        p.fetch_monthly_dataset = boom
        run174.install(p)
        with self.assertRaisesRegex(RuntimeError, "boom"):
            p.fetch_monthly_dataset("start", "end")
        self.assertIs(original_query, p._query_notion_db_with_retry)
        self.assertEqual(500, p.MONTHLY_DIGEST_MAX_ITEMS)

    def test_install_is_idempotent(self):
        p = fake_pipeline(pages_for(1))
        run174.install(p)
        wrapped = p.fetch_monthly_dataset
        run174.install(p)
        self.assertIs(wrapped, p.fetch_monthly_dataset)

    def test_missing_query_hook_fails_loudly(self):
        p = fake_pipeline(pages_for(1))
        p._query_notion_db_with_retry = None
        with self.assertRaisesRegex(RuntimeError, "_query_notion_db_with_retry"):
            run174.install(p)

    def test_production_entrypoint_installs_run174_after_run173(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "production_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("import run174_monthly_digest_integrity", text)
        pos173 = text.index("run173_operational_yield.install(pipeline_module)")
        pos174 = text.index("run174_monthly_digest_integrity.install(pipeline_module)")
        pos_bridge = text.index("reader_value_review_bridge.install(pipeline_module)")
        self.assertLess(pos173, pos174)
        self.assertLess(pos174, pos_bridge)

    def test_run174_has_no_model_call_surface(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "run174_monthly_digest_integrity.py").read_text(encoding="utf-8")
        self.assertNotIn("_generate_via_chat", text)
        self.assertNotIn("GEMINI_API_KEY", text)


if __name__ == "__main__":
    unittest.main()
