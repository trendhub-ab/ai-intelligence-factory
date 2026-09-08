from __future__ import annotations

import inspect
import sys
import types
import unittest
from unittest.mock import patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Response = object
    requests_stub.RequestException = Exception
    requests_stub.request = lambda *args, **kwargs: None
    requests_stub.get = lambda *args, **kwargs: None
    requests_stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

import run292_note_rendered_body_audit as audit


class Run292RenderedExpectationTests(unittest.TestCase):
    def _manuscript(self) -> str:
        return (
            "導入です。\n\n"
            "## 実装例\n"
            "```python\n"
            "def recommend(user_id):\n"
            "    return 'candidate'\n"
            "```\n\n"
            "### Sources / Evidence\n"
            "- source A\n\n"
            "### 調査と判断の時間を減らしたい方へ\n"
            "CTAです。"
        )

    def test_renderer_expected_text_preserves_visible_fenced_code(self) -> None:
        manuscript = self._manuscript()
        rendered = audit._rendered_visible_text(manuscript)
        legacy = audit.base._normalized_visible(audit.base.note_base._plain_manuscript_text(manuscript))
        self.assertIn("recommend(user_id)", rendered)
        self.assertNotIn("recommend(user_id)", legacy)
        self.assertGreater(len(rendered), len(legacy))

    def test_rendered_body_passes_same_boundary_footer_and_title_guards(self) -> None:
        manuscript = self._manuscript()
        actual = audit._rendered_visible_text(manuscript)
        metrics = audit._body_text_metrics(actual, manuscript, "別のタイトル")
        self.assertEqual(metrics["expectation_mode"], "safe_html_renderer")
        self.assertTrue(metrics["prefix_match"])
        self.assertTrue(metrics["suffix_match"])
        self.assertTrue(metrics["sources_before_cta"])
        self.assertFalse(metrics["duplicate_title_prefix"])
        self.assertEqual(metrics["visible_length_ratio"], 1.0)
        self.assertGreater(metrics["renderer_delta_chars"], 0)

    def test_real_content_mismatch_still_fails_closed_with_safe_metrics_only(self) -> None:
        manuscript = self._manuscript()
        with self.assertRaises(audit.Run292AuditDiagnosticError) as caught:
            audit._body_text_metrics("全く異なる短い本文", manuscript, "非公開タイトル")
        exc = caught.exception
        self.assertIn(exc.code, {"presentation_boundary_mismatch", "visible_length_ratio_out_of_bounds"})
        for forbidden in ("actual_text", "expected_text", "manuscript", "title", "draft_url"):
            self.assertNotIn(forbidden, exc.safe_metrics)
        self.assertIn("visible_length_ratio", exc.safe_metrics)
        self.assertIn("common_prefix_ratio", exc.safe_metrics)
        self.assertIn("common_suffix_ratio", exc.safe_metrics)

    def test_duplicate_title_and_footer_guards_remain_fail_closed(self) -> None:
        manuscript = self._manuscript()
        rendered = audit._rendered_visible_text(manuscript)
        with self.assertRaises(audit.Run292AuditDiagnosticError) as duplicate:
            audit._body_text_metrics("非公開タイトル " + rendered, manuscript, "非公開タイトル")
        self.assertEqual(duplicate.exception.code, "duplicate_title_prefix")

        reversed_footer = rendered.replace(
            "Sources / Evidence source A 調査と判断の時間を減らしたい方へ CTAです。",
            "調査と判断の時間を減らしたい方へ CTAです。 Sources / Evidence source A",
        )
        with self.assertRaises(audit.Run292AuditDiagnosticError) as footer:
            audit._body_text_metrics(reversed_footer, manuscript, "別タイトル")
        self.assertEqual(footer.exception.code, "footer_order_mismatch")


class Run292ExecutionBoundaryTests(unittest.TestCase):
    def test_wrapper_restores_run291_metric_function_after_execution(self) -> None:
        original = audit.base._body_text_metrics
        with patch.object(audit.base, "run", return_value={"status": "audit_passed"}) as base_run:
            result = audit.run(confirm="AUDIT_NOTE_DRAFT", sync_id="a" * 32)
            base_run.assert_called_once()
        self.assertEqual(result["status"], "audit_passed")
        self.assertIs(audit.base._body_text_metrics, original)

    def test_safe_failure_result_exposes_no_unpublished_content_or_route(self) -> None:
        result = audit._safe_failure_result(
            "b" * 32,
            "presentation_boundary_mismatch",
            {"body_visible_chars": 123, "actual_text": "secret", "expected_text": "secret2", "title": "secret3"},
        )
        self.assertEqual(result["status"], "audit_failed_safe")
        self.assertTrue(result["read_only"])
        self.assertTrue(result["zero_gemini_calls"])
        self.assertFalse(result["draft_mutation"])
        self.assertFalse(result["public_release"])
        for forbidden in ("actual_text", "expected_text", "manuscript", "title", "draft_url"):
            self.assertNotIn(forbidden, result)

    def test_module_has_no_browser_mutation_publication_screenshot_or_network_write_surface(self) -> None:
        source = inspect.getsource(audit)
        for forbidden in (
            ".click(", ".fill(", "keyboard.press", "keyboard.insert_text",
            "page.screenshot(", "requests.post(", "requests.patch(",
            "_paste_manuscript(", "_save_draft_and_verify(", "_mark_draft_created(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
