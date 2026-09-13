import inspect
import unittest

import run180_eyecatch_semantic_layout as r180
import run422_rubygems_pinned_canonical_copy as r422


class Run422PinnedCanonicalCopyTests(unittest.TestCase):
    def test_pinned_title_preserves_required_source_tokens(self):
        source = r180._source_title_for_direction(r422.r418.EXPECTED_NOTE_TITLE)
        self.assertEqual(
            r180._validate_eyecatch_title(source, r422.PINNED_EYECATCH_TITLE),
            r422.PINNED_EYECATCH_TITLE,
        )
        required = {token.casefold() for token in r180._required_source_tokens(source)}
        folded = r422.PINNED_EYECATCH_TITLE.casefold()
        for token in required:
            self.assertIn(token, folded)

    def test_copy_is_short_and_source_bounded(self):
        self.assertLessEqual(len(r422.PINNED_EYECATCH_TITLE), 45)
        self.assertLessEqual(len(r422.PINNED_SUBHEADLINE), 24)
        self.assertIn("OpenAI", r422.PINNED_EYECATCH_TITLE)
        self.assertIn("RubyGems", r422.PINNED_EYECATCH_TITLE)
        self.assertIn("権限管理", r422.PINNED_EYECATCH_TITLE)
        self.assertIn(r422.PINNED_HIGHLIGHT, r422.PINNED_EYECATCH_TITLE)

    def test_main_copy_accepts_exactly_two_or_three_lines(self):
        two = {"title_lines": ["OpenAIエージェントとRubyGems、", "権限管理の境界線"]}
        three = {"title_lines": ["OpenAIエージェントと", "RubyGems、", "権限管理の境界線"]}
        self.assertEqual(len(r422._require_bounded_title_lines(two)["title_lines"]), 2)
        self.assertEqual(len(r422._require_bounded_title_lines(three)["title_lines"]), 3)

    def test_main_copy_rejects_one_or_four_lines(self):
        with self.assertRaises(r422.r418.Run418Error):
            r422._require_bounded_title_lines({"title_lines": [r422.PINNED_EYECATCH_TITLE]})
        with self.assertRaises(r422.r418.Run418Error):
            r422._require_bounded_title_lines({"title_lines": ["OpenAI", "エージェント", "RubyGems", "権限管理"]})

    def test_render_path_has_zero_model_and_no_raw_renderer(self):
        source = inspect.getsource(r422)
        self.assertNotIn("_generate_via_chat", source)
        self.assertNotIn("_request_layout_plan", source)
        self.assertNotIn("generate_note_editorial_eyecatch", source)
        self.assertIn("_render_with_validated_plan", source)
        self.assertIn('"gemini_calls": 0', source)

    def test_exact_target_and_private_draft_contract_remain(self):
        source = inspect.getsource(r422.render_and_attach)
        self.assertIn("require_broken=True", source)
        self.assertIn("_upload_replace", source)
        refresh = inspect.getsource(r422.refresh_existing_private_draft)
        self.assertIn("r418.refresh_existing_private_draft", refresh)

    def test_no_public_release_surface(self):
        source = inspect.getsource(r422)
        for token in ("publish_note", "click_publish", "release_note", "公開する"):
            self.assertNotIn(token, source)
        self.assertIn('"public_release": False', source)


if __name__ == "__main__":
    unittest.main()
