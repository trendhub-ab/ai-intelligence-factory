from __future__ import annotations

import inspect
import unittest

import run302_genrec_publication_reconcile as r302


class Run302PureTests(unittest.TestCase):
    def test_note_id_is_derived_only_from_editor_route(self):
        self.assertEqual(
            r302._note_id_from_edit_route("https://editor.note.com/notes/nabc123/edit"),
            "nabc123",
        )
        with self.assertRaises(r302.Run302Error):
            r302._note_id_from_edit_route("https://note.com/trendhub_biz/n/nabc123")

    def test_public_body_contract_requires_exact_summary_and_order(self):
        text = f"""{r302.r296.INTRO_HEADING_NEW}
{r302.r301.EXPECTED_SUMMARY}
なぜ重要？
重要です。
結論は？
結論です。
Sources / Evidence
source
{r302.r296.CTA_HEADING}
{r302.r296.CTA_BODY}
{r302.r296.CTA_LINK_LABEL}
"""
        metrics = r302._public_body_metrics(text, r302.r296.GENREC_SOURCE_TITLE)
        self.assertEqual(metrics["summary_count"], 1)
        self.assertTrue(metrics["summary_order_valid"])
        self.assertTrue(metrics["what_label_absent"])
        self.assertTrue(metrics["sources_before_cta"])

    def test_removed_label_reappearance_is_fatal(self):
        text = f"""{r302.r296.INTRO_HEADING_NEW}
{r302.r296.REMOVE_SUMMARY_LABEL}
{r302.r301.EXPECTED_SUMMARY}
なぜ重要？
結論は？
Sources / Evidence
{r302.r296.CTA_HEADING}
{r302.r296.CTA_BODY}
{r302.r296.CTA_LINK_LABEL}
"""
        with self.assertRaises(r302.Run302Error):
            r302._public_body_metrics(text, r302.r296.GENREC_SOURCE_TITLE)


class Run302SafetyTests(unittest.TestCase):
    def test_no_note_mutation_or_publication_surface(self):
        source = inspect.getsource(r302).lower()
        for forbidden in (
            "page.click(",
            "keyboard.press(",
            "_save_draft_and_verify(",
            "_paste_manuscript(",
            "_upload_header_image(",
            "publish_note",
            "/new",
            "generate_content(",
            "_generate_via_chat(",
        ):
            self.assertNotIn(forbidden, source)

    def test_exact_target_is_fixed(self):
        self.assertEqual(r302.TARGET_SYNC_ID, "3bd479ffdca9817f926aeaffbb779c4b")
        self.assertEqual(r302.AUTHOR_SLUG, "trendhub_biz")


if __name__ == "__main__":
    unittest.main()
