from __future__ import annotations

import inspect
import unittest

import run298_header_readonly_diagnostics as diag


class Run298HeaderReadOnlyDiagnosticTests(unittest.TestCase):
    def test_route_hash_exposes_no_route(self):
        value = diag._safe_route_hash("https://editor.note.com/notes/abc123/edit")
        self.assertEqual(len(value), 12)
        self.assertNotIn("abc123", value)
        self.assertEqual(diag._safe_route_hash("https://note.com/new"), "")

    def test_module_has_no_browser_mutation_or_publication_surface(self):
        source = inspect.getsource(diag).lower()
        forbidden = (
            ".click(", ".fill(", "set_input_files", "set_files(",
            "_paste_manuscript", "_upload_header_image", "_save_draft_and_verify",
            "screenshot", "note.com/new", "generate_content", "client.models",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_clickability_metrics_are_numeric_only(self):
        class FakeTitle:
            def bounding_box(self):
                return {"y": 400}

        class FakePage:
            def evaluate(self, _script, _title_y):
                return {
                    "large_media_candidate_count": 1,
                    "large_media_clickable_ancestor_count": 0,
                    "large_media_pointer_ancestor_count": 1,
                }

        result = diag._header_clickability_metrics(FakePage(), FakeTitle())
        self.assertEqual(result["large_media_candidate_count"], 1)
        self.assertEqual(result["large_media_clickable_ancestor_count"], 0)
        self.assertEqual(result["large_media_pointer_ancestor_count"], 1)


if __name__ == "__main__":
    unittest.main()