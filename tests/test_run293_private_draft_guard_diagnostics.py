from __future__ import annotations

import inspect
import unittest

import run292_note_rendered_body_audit as audit


class Run293NonBodyDiagnosticMappingTests(unittest.TestCase):
    def test_known_fixed_non_body_errors_map_to_allowlisted_codes(self) -> None:
        cases = {
            "note authentication is not active": "note_auth_inactive",
            "Matched page is not a confirmed note editor route": "editor_route_invalid",
            "Private draft title does not match the requested article": "draft_title_mismatch",
            "Could not inspect private draft semantic structure": "semantic_structure_read_failed",
            "Private draft contains a body-level H1": "body_h1_present",
            "Private draft lost its expected heading structure": "heading_structure_lost",
            "Private draft eyecatch persistence could not be confirmed": "eyecatch_persistence_unconfirmed",
            "Private draft editor geometry is unavailable": "editor_geometry_unavailable",
            "Private draft editor content width is unexpectedly narrow": "editor_width_narrow",
            "No private note edit route is present in persistent Chrome history": "chrome_history_no_routes",
            "The requested private draft could not be matched safely from local Chrome history": "draft_not_matched_from_history",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                exc = audit.base.PrivateDraftAuditError(message)
                self.assertEqual(audit._safe_non_body_guard_code(exc), expected)

    def test_confirmation_error_maps_without_copying_dynamic_exception_text(self) -> None:
        exc = audit.base.PrivateDraftAuditError(
            f"Confirmation must equal {audit.base.CONFIRM_TOKEN}"
        )
        self.assertEqual(audit._safe_non_body_guard_code(exc), "confirmation_invalid")

    def test_unknown_private_draft_error_remains_generic_fail_closed(self) -> None:
        secret = "unexpected unpublished detail /notes/private-secret/edit"
        exc = audit.base.PrivateDraftAuditError(secret)
        code = audit._safe_non_body_guard_code(exc)
        self.assertEqual(code, "non_body_guard_failed")
        result = audit._safe_failure_result("a" * 32, code)
        serialized = repr(result)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("private-secret", serialized)

    def test_mapping_has_no_unpublished_content_values_or_urls(self) -> None:
        for message, code in audit._NON_BODY_GUARD_CODES.items():
            with self.subTest(code=code):
                self.assertTrue(code)
                self.assertNotIn("http://", code)
                self.assertNotIn("https://", code)
                self.assertNotIn("/notes/", code)
                self.assertNotIn("manuscript", code)
                self.assertNotIn("actual_text", code)
                self.assertNotIn("expected_text", code)
                # Fixed error strings may describe a guard, but must never carry a route.
                self.assertNotIn("/notes/", message)

    def test_run293_diagnostics_do_not_add_mutation_screenshot_or_model_surface(self) -> None:
        source = inspect.getsource(audit)
        for forbidden in (
            ".click(", ".fill(", "keyboard.press", "keyboard.insert_text",
            "page.screenshot(", "requests.post(", "requests.patch(",
            "_paste_manuscript(", "_save_draft_and_verify(", "_mark_draft_created(",
            "generate_content", "google.generativeai", "publish_note",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
