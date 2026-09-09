from __future__ import annotations

import inspect
import unittest

import run296_editorial_format_v2 as r296
import run299_genrec_body_structure_diagnostic as diag


class Run299BodyStructureDiagnosticTests(unittest.TestCase):
    def test_marker_counts_are_numeric_only(self):
        result = diag._counts(
            f"どんな内容？ Sources / Evidence 有料サブスクのご案内 {r296.CTA_LINK_LABEL}"
        )
        self.assertEqual(result["new_intro_count"], 1)
        self.assertEqual(result["sources_heading_count"], 1)
        self.assertEqual(result["cta_heading_count"], 1)
        self.assertEqual(result["cta_link_label_count"], 1)

    def test_module_has_no_browser_mutation_or_publication_surface(self):
        source = inspect.getsource(diag).lower()
        forbidden = (
            ".click(", ".fill(", "set_input_files", "set_files(", "_paste_manuscript",
            "_upload_header_image", "_save_draft_and_verify", "note.com/new",
            "generate_content", "client.models", "page.screenshot",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_result_contract_declares_read_only(self):
        source = inspect.getsource(diag.collect)
        self.assertIn('"read_only": True', source)
        self.assertIn('"draft_mutation": False', source)
        self.assertIn('"public_release": False', source)
        self.assertIn('"zero_gemini_calls": True', source)


if __name__ == "__main__":
    unittest.main()
