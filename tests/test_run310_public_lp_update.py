from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run310_public_lp_update as run310

ROOT = Path(__file__).resolve().parents[1]


class Run310PublicLpUpdateTests(unittest.TestCase):
    def test_exact_target_and_confirmation_are_hard_bound(self) -> None:
        self.assertEqual(run310.TARGET_NOTE_ID, "ned673e381ef8")
        self.assertEqual(run310.CONFIRM_TOKEN, "UPDATE_PUBLIC_LP_NED673E381EF8")
        self.assertEqual(run310.TARGET_PUBLIC_URL, "https://note.com/trendhub_biz/n/ned673e381ef8")
        self.assertEqual(run310.TARGET_EDITOR_URL, "https://editor.note.com/notes/ned673e381ef8/edit/")
        self.assertEqual(run310.TARGET_PUBLISH_URL, "https://editor.note.com/notes/ned673e381ef8/publish/")

    def test_handoff_is_current_clickable_and_product_hunt_free(self) -> None:
        title, body = run310._load_handoff()
        self.assertEqual(title, run310.EXPECTED_TITLE)
        self.assertTrue(body.startswith("## 「このAI、使える！」"))
        for marker in run310.REQUIRED_PUBLIC_MARKERS:
            self.assertTrue(marker in body or marker in title)
        self.assertNotIn("Product Hunt", body)
        self.assertIn("[月額1,980円の内容を見る](https://note.com/trendhub_biz/membership)", body)

    def test_updater_uses_only_observed_public_update_controls(self) -> None:
        source = inspect.getsource(run310.update_public_lp)
        self.assertIn('_unique_button(page, "公開に進む").click()', source)
        self.assertIn('_unique_button(page, "更新する").click()', source)
        self.assertIn("current_title != LEGACY_TITLE", source)
        self.assertIn("_verify_public(page, title)", source)
        for forbidden in ("#生成AI", "#AI活用", "#個人開発", "マガジン", "メンバーシップ設定"):
            self.assertNotIn(forbidden, source)

    def test_public_verification_requires_clickable_membership_destination(self) -> None:
        source = inspect.getsource(run310._verify_public)
        self.assertIn('a[href*="note.com/trendhub_biz/membership"]', source)
        self.assertIn("LEGACY_TITLE", source)
        self.assertIn("REQUIRED_PUBLIC_MARKERS", source)

    def test_workflow_is_exact_and_manual_only(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-public-lp-update.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("UPDATE_PUBLIC_LP_NED673E381EF8", workflow)
        self.assertIn("run310_public_lp_update.py", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("ned673e381ef8", workflow)


if __name__ == "__main__":
    unittest.main()
