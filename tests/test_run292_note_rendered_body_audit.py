from __future__ import annotations

import inspect
from pathlib import Path
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

        footer_manuscript = (
            ("十分に長い前置きです。" * 20)
            + "\n\n"
            + manuscript
            + "\n\n"
            + ("末尾の境界を安定させる確認文です。" * 20)
        )
        footer_rendered = audit._rendered_visible_text(footer_manuscript)
        source = "Sources / Evidence"
        cta = "調査と判断の時間を減らしたい方へ"
        source_index = footer_rendered.find(source)
        self.assertGreater(source_index, 64)
        self.assertGreater(len(footer_rendered) - source_index, 64)
        cta_before_source = footer_rendered[:source_index] + f"{cta} PRE " + footer_rendered[source_index:]
        with self.assertRaises(audit.Run292AuditDiagnosticError) as footer:
            audit._body_text_metrics(cta_before_source, footer_manuscript, "別タイトル")
        self.assertEqual(footer.exception.code, "footer_order_mismatch")


class Run292CanonicalIntegrationTests(unittest.TestCase):
    def test_canonical_snapshot_match_is_required(self) -> None:
        snapshot = {
            "type": "root",
            "children": [
                {"type": "element", "tag": "p", "attrs": {}, "children": [{"type": "text", "text": "10秒"}]}
            ],
        }
        metrics = audit._canonical_snapshot_metrics(snapshot, "10秒")
        self.assertTrue(metrics["canonical_match"])
        self.assertEqual(metrics["unsupported_expected_node_count"], 0)
        self.assertEqual(metrics["unsupported_actual_node_count"], 0)
        self.assertEqual(metrics["expected_canonical_node_count"], 3)
        self.assertEqual(metrics["actual_canonical_node_count"], 3)
        self.assertIn("Paragraph", metrics["expected_node_counts"])
        self.assertIn("Paragraph", metrics["actual_node_counts"])

    def test_canonical_snapshot_semantic_change_fails_closed(self) -> None:
        snapshot = {
            "type": "root",
            "children": [
                {"type": "element", "tag": "p", "attrs": {}, "children": [{"type": "text", "text": "99秒"}]}
            ],
        }
        with self.assertRaises(audit.Run292AuditDiagnosticError) as caught:
            audit._canonical_snapshot_metrics(snapshot, "10秒")
        self.assertEqual(caught.exception.code, "text_value_mismatch")
        self.assertNotIn("99秒", repr(caught.exception.safe_metrics))
        self.assertNotIn("10秒", repr(caught.exception.safe_metrics))

    def test_unknown_dom_is_categorical_content_free_and_structurally_diagnostic(self) -> None:
        snapshot = {
            "type": "root",
            "children": [
                {
                    "type": "element",
                    "tag": "div",
                    "attrs": {"title": "PRIVATE-ATTR-SENTINEL"},
                    "children": [
                        {"type": "element", "tag": "section", "attrs": {}, "children": [{"type": "text", "text": "PRIVATE-BODY-SENTINEL"}]}
                    ],
                }
            ],
        }
        with self.assertRaises(audit.Run292AuditDiagnosticError) as caught:
            audit._canonical_snapshot_metrics(snapshot, "本文")
        self.assertEqual(caught.exception.code, "unsupported_note_dom")
        metrics = caught.exception.safe_metrics
        self.assertFalse(metrics["canonical_match"])
        self.assertEqual(metrics["unsupported_actual_node_count"], 1)
        self.assertEqual(metrics["dom_diagnostic_category"], "unknown_dom_tag")
        self.assertEqual(metrics["unknown_dom_tags"], ["div", "section"])
        self.assertEqual(metrics["unknown_dom_tag_counts"], {"div": 1, "section": 1})
        self.assertEqual(metrics["dom_tag_counts"], {"div": 1, "section": 1})
        self.assertEqual(metrics["snapshot_element_node_count"], 2)
        self.assertEqual(metrics["snapshot_text_node_count"], 1)
        self.assertEqual(metrics["snapshot_total_node_count"], 3)
        self.assertEqual(metrics["expected_canonical_node_count"], 3)
        self.assertEqual(metrics["actual_canonical_node_count"], 0)
        rendered = repr(metrics)
        self.assertNotIn("PRIVATE-BODY-SENTINEL", rendered)
        self.assertNotIn("PRIVATE-ATTR-SENTINEL", rendered)


class Run292ExecutionBoundaryTests(unittest.TestCase):
    def test_wrapper_restores_run291_metric_and_page_functions_after_execution(self) -> None:
        original_metric = audit.base._body_text_metrics
        original_page = audit.base._audit_current_page
        with patch.object(audit.base, "run", return_value={"status": "audit_passed"}) as base_run:
            result = audit.run(confirm="AUDIT_NOTE_DRAFT", sync_id="a" * 32)
            base_run.assert_called_once()
        self.assertEqual(result["status"], "audit_passed")
        self.assertIs(audit.base._body_text_metrics, original_metric)
        self.assertIs(audit.base._audit_current_page, original_page)

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

    def test_private_draft_workflow_summary_includes_only_content_free_canonical_diagnostics(self) -> None:
        workflow = Path('.github/workflows/note-private-draft-audit.yml').read_text(encoding='utf-8')
        for key in (
            'canonical_match', 'dom_diagnostic_category', 'unknown_dom_tags',
            'unknown_dom_tag_counts', 'dom_tag_counts', 'snapshot_element_node_count',
            'snapshot_text_node_count', 'snapshot_total_node_count',
            'expected_canonical_node_count', 'actual_canonical_node_count',
            'unsupported_expected_node_count', 'unsupported_actual_node_count',
        ):
            self.assertIn(f"'{key}'", workflow)

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
