from __future__ import annotations

import inspect
import re
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

import run292_note_rendered_body_audit as audit
import run295_note_private_draft_audit as final_audit


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

    def test_account_proof_cause_chain_maps_to_safe_stage_only(self) -> None:
        cases = {
            "note authentication is not active for the expected account": "auth_inactive",
            "note profile settings could not be opened for the expected account": "settings_route_unproven",
            "expected note creator identity could not be inspected": "creator_selector_unproven",
            "expected note creator identity could not be proven": "creator_selector_unproven",
            "persistent note session belongs to an unexpected creator account": "creator_mismatch",
            "note authentication expired during account ownership proof": "auth_inactive",
            "expected note account ownership control could not be proven": "profile_ownership_unproven",
            "persistent note session does not own the expected note profile": "profile_ownership_unproven",
        }
        for source_message, expected_stage in cases.items():
            with self.subTest(source_message=source_message):
                source_exc = audit.base.note_base.NoteDraftError(source_message)
                outer = audit.base.PrivateDraftAuditError(
                    "Expected note account ownership could not be proven"
                )
                outer.__cause__ = source_exc
                self.assertEqual(final_audit._safe_account_proof_stage(outer), expected_stage)

    def test_unknown_account_cause_emits_no_dynamic_stage(self) -> None:
        secret = "private account detail that must never escape"
        source_exc = audit.base.note_base.NoteDraftError(secret)
        outer = audit.base.PrivateDraftAuditError(
            "Expected note account ownership could not be proven"
        )
        outer.__cause__ = source_exc
        self.assertIsNone(final_audit._safe_account_proof_stage(outer))

    def test_final_result_layer_adds_only_allowlisted_account_stage(self) -> None:
        source = inspect.getsource(final_audit.main)
        self.assertIn("_safe_account_proof_stage", source)
        self.assertIn('metrics["account_proof_stage"] = account_stage', source)
        self.assertNotIn("str(exc.__cause__)", source)

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

    def test_mapping_uses_non_content_categorical_codes_and_no_routes(self) -> None:
        code_pattern = re.compile(r"^[a-z0-9_]{1,64}$")
        for message, code in audit._NON_BODY_GUARD_CODES.items():
            with self.subTest(code=code):
                self.assertRegex(code, code_pattern)
                self.assertNotIn("http://", code)
                self.assertNotIn("https://", code)
                self.assertNotIn("/", code)
                self.assertNotIn("\\", code)
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
