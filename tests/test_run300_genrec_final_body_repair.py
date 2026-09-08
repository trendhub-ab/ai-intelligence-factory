from __future__ import annotations

import inspect
import unittest

import run296_editorial_format_v2 as r296
import run300_genrec_final_body_repair as run300


class Run300FinalBodyRepairTests(unittest.TestCase):
    def test_exact_duplicate_state_is_recognized(self):
        text = "\n".join([
            r296.INTRO_HEADING_OLD,
            r296.REMOVE_SUMMARY_LABEL,
            "Sources / Evidence",
            r296.INTRO_HEADING_NEW,
            "Sources / Evidence",
            r296.CTA_HEADING,
            r296.CTA_LINK_LABEL,
        ])
        self.assertEqual(run300._classify_current_body(text), "run298_duplicate")

    def test_exact_canonical_state_is_recognized(self):
        text = "\n".join([
            r296.INTRO_HEADING_NEW,
            "Sources / Evidence",
            r296.CTA_HEADING,
            r296.CTA_LINK_LABEL,
        ])
        self.assertEqual(run300._classify_current_body(text), "canonical")

    def test_ambiguous_or_partial_state_fails_closed(self):
        text = "\n".join([
            r296.INTRO_HEADING_NEW,
            r296.INTRO_HEADING_OLD,
            "Sources / Evidence",
            r296.CTA_HEADING,
            r296.CTA_LINK_LABEL,
        ])
        with self.assertRaises(run300.Run300Error):
            run300._classify_current_body(text)

    def test_exact_selection_is_verified_before_delete(self):
        source = inspect.getsource(run300._strict_clear_body)
        self.assertLess(source.index("_select_exact_body_contents"), source.index('press("Backspace")'))
        self.assertIn("body_not_empty_after_exact_delete", source)

    def test_clear_precedes_paste_and_save(self):
        source = inspect.getsource(run300.repair_and_audit)
        self.assertLess(source.index("_strict_clear_body"), source.index("_paste_canonical_once"))
        self.assertLess(source.index("_paste_canonical_once"), source.index("_save_draft_and_verify"))

    def test_run300_never_changes_header(self):
        source = inspect.getsource(run300)
        self.assertNotIn("_upload_header_image(", source)
        self.assertNotIn("set_input_files", source)
        self.assertNotIn("expect_file_chooser", source)
        self.assertIn("header_changed_during_body_only_repair", source)

    def test_exact_1280x670_is_hard_gated(self):
        source = inspect.getsource(run300._require_1280x670_source)
        self.assertIn("(1280, 670)", source)
        self.assertIn("source_eyecatch_wrong_dimensions", source)

    def test_no_new_draft_publication_or_model_surface(self):
        source = inspect.getsource(run300).lower()
        self.assertNotIn("https://note.com/new", source)
        self.assertNotIn("_create_browser_draft(", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("client.models", source)
        self.assertNotIn("publish_note", source)


if __name__ == "__main__":
    unittest.main()
