from __future__ import annotations

import inspect
import sys
import types
import unittest

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

import run294_note_eyecatch_persistence_diagnostics as audit


class Run294EyecatchClassificationTests(unittest.TestCase):
    def test_large_header_media_without_legacy_control_flags_selector_drift(self) -> None:
        metrics = {
            "large_top_img_count": 1,
            "large_top_background_count": 0,
            "eyecatch_exact_control_visible_count": 0,
            "image_labeled_control_visible_count": 0,
            "image_add_control_visible_count": 0,
        }
        self.assertEqual(
            audit._classify_eyecatch_state(metrics),
            "eyecatch_present_selector_drift_likely",
        )

    def test_visible_add_control_without_header_media_flags_missing_likely(self) -> None:
        metrics = {
            "large_top_img_count": 0,
            "large_top_background_count": 0,
            "eyecatch_exact_control_visible_count": 0,
            "image_labeled_control_visible_count": 1,
            "image_add_control_visible_count": 1,
        }
        self.assertEqual(audit._classify_eyecatch_state(metrics), "eyecatch_missing_likely")

    def test_no_media_and_no_controls_stays_ambiguous(self) -> None:
        metrics = {
            "large_top_img_count": 0,
            "large_top_background_count": 0,
            "eyecatch_exact_control_visible_count": 0,
            "image_labeled_control_visible_count": 0,
            "image_add_control_visible_count": 0,
        }
        self.assertEqual(
            audit._classify_eyecatch_state(metrics),
            "eyecatch_missing_or_ui_ambiguous",
        )

    def test_control_without_media_proof_does_not_claim_image_presence(self) -> None:
        metrics = {
            "large_top_img_count": 0,
            "large_top_background_count": 0,
            "eyecatch_exact_control_visible_count": 0,
            "image_labeled_control_visible_count": 2,
            "image_add_control_visible_count": 0,
        }
        self.assertEqual(
            audit._classify_eyecatch_state(metrics),
            "eyecatch_control_without_media_proof",
        )


class Run294ExecutionBoundaryTests(unittest.TestCase):
    def test_module_has_no_mutation_screenshot_model_or_public_release_surface(self) -> None:
        source = inspect.getsource(audit)
        forbidden = (
            ".click(",
            ".fill(",
            "set_input_files(",
            "keyboard.press",
            "keyboard.insert_text",
            "page.screenshot(",
            "requests.post(",
            "requests.patch(",
            "_upload_header_image(",
            "_save_draft_and_verify(",
            "_mark_draft_created(",
            "generate_content",
            "google.generativeai",
            "publish_note",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_diagnostics_never_read_or_emit_image_src_or_dom_html(self) -> None:
        source = inspect.getsource(audit)
        for forbidden in (
            "getAttribute('src')",
            'getAttribute("src")',
            ".currentSrc",
            ".outerHTML",
            ".innerHTML",
            "draft_url",
            "actual_text",
            "expected_text",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_wrapper_restores_original_page_audit_even_when_base_run_raises(self) -> None:
        original_audit = audit.base._audit_current_page
        original_run = audit.base292.run

        def sentinel(*args, **kwargs):
            raise audit.base.PrivateDraftAuditError("sentinel")

        audit.base292.run = sentinel
        try:
            with self.assertRaises(audit.base.PrivateDraftAuditError):
                audit.run(confirm="AUDIT_NOTE_DRAFT", sync_id="a" * 32)
            self.assertIs(audit.base._audit_current_page, original_audit)
        finally:
            audit.base292.run = original_run
            audit.base._audit_current_page = original_audit

    def test_safe_failure_result_contains_only_categorical_and_numeric_diagnostics(self) -> None:
        metrics = {
            "large_top_img_count": 1,
            "max_top_media_width": 720,
            "title_geometry_available": True,
        }
        result = audit._safe_failure_result(
            "a" * 32,
            "eyecatch_present_selector_drift_likely",
            metrics,
        )
        self.assertFalse(result["success"])
        self.assertTrue(result["zero_gemini_calls"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["draft_mutation"])
        self.assertFalse(result["public_release"])
        self.assertEqual(result["large_top_img_count"], 1)
        self.assertNotIn("draft_url", result)
        self.assertNotIn("manuscript", result)


if __name__ == "__main__":
    unittest.main()
