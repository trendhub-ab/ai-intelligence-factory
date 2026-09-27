from __future__ import annotations

import inspect
import unittest

import eyecatch_badge_taxonomy as taxonomy
import run181_eyecatch_visual_balance as run181
import run_openai2015_current_eyecatch_resync as repair


class OpenAI2015CurrentEyecatchResyncTests(unittest.TestCase):
    def test_historical_openai_article_uses_origin_badge_and_hook(self):
        self.assertEqual(
            taxonomy.classify_badge(repair.TITLE_LINES[0], repair.SUMMARY, repair.CATEGORY),
            "原点を知る",
        )
        self.assertEqual(
            run181._editorial_hook(repair.TITLE_LINES[0], repair.SUMMARY, repair.CATEGORY),
            "原点から、何が見えるのか？",
        )

    def test_fixed_eyecatch_copy_is_historical_not_adoption_framing(self):
        self.assertEqual(
            repair.EYECATCH_TITLE,
            "OpenAIは非営利から始まった。2015年の原点を読み直す",
        )
        forbidden = ("導入", "PoC", "本番移行", "新たな基準点", "論文をやさしく")
        combined = "\n".join(
            [repair.EYECATCH_TITLE, *repair.TITLE_LINES, *repair.SUBHEAD_LINES]
        )
        for token in forbidden:
            self.assertNotIn(token, combined)

    def test_one_off_resync_contains_no_model_or_new_draft_path(self):
        source = inspect.getsource(repair)
        forbidden = (
            "_generate_via_chat(",
            "call_gemini(",
            "generateContent",
            "https://note.com/new",
            "_create_browser_draft(",
        )
        for token in forbidden:
            self.assertNotIn(token, source)
        self.assertIn("new_draft_created", source)
        self.assertIn("public_release", source)
        self.assertIn("zero_gemini_calls", source)

    def test_runtime_state_asset_contract_is_explicit(self):
        self.assertEqual(repair.ASSET_BRANCH, "runtime-state")
        self.assertEqual(repair.ASSET_BASE, "OpenAI_2015.png")
        self.assertEqual(repair.repair.SYNC_ID, "3e8479ffdca9812e9661f337a84b1df4")


if __name__ == "__main__":
    unittest.main()
