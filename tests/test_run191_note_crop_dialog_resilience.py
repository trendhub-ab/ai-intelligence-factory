from __future__ import annotations

import inspect
import unittest

import run191_note_crop_dialog_resilience as run191


class Run191NoteCropDialogResilienceTests(unittest.TestCase):
    def test_accepts_explicit_completion_semantics(self) -> None:
        for text in (
            "保存",
            "保存する",
            "完了",
            "この画像を使用",
            "変更を適用",
            "confirm crop",
            "save image",
        ):
            with self.subTest(text=text):
                self.assertTrue(run191._is_safe_completion_semantic(text))

    def test_rejects_public_release_and_cancel_semantics(self) -> None:
        for text in (
            "公開する",
            "投稿する",
            "publish",
            "release",
            "キャンセル",
            "閉じる",
            "削除",
            "back",
        ):
            with self.subTest(text=text):
                self.assertFalse(run191._is_safe_completion_semantic(text))

    def test_empty_or_unlabelled_control_is_not_guessed(self) -> None:
        self.assertFalse(run191._is_safe_completion_semantic(""))
        self.assertFalse(run191._is_safe_completion_semantic("button"))
        self.assertFalse(run191._is_safe_completion_semantic("zoom in"))

    def test_overlay_searches_all_modal_roots_and_stays_fail_closed(self) -> None:
        source = inspect.getsource(run191)
        self.assertIn('[role="dialog"], [aria-modal="true"]', source)
        self.assertIn("multiple safe completion controls", source)
        self.assertIn("no unique safe save/complete control", source)
        self.assertIn("run188._finish_crop_dialog = _finish_crop_dialog", source)
        self.assertNotIn("公開する", source.replace('"公開する",', ''))


if __name__ == "__main__":
    unittest.main()
