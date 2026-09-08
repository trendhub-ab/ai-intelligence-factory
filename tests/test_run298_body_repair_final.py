from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import run298_body_repair_final as repair


class _Keyboard:
    def __init__(self):
        self.presses = []

    def press(self, value):
        self.presses.append(value)


class _Page:
    def __init__(self):
        self.keyboard = _Keyboard()

    def wait_for_timeout(self, ms):
        return None


class _Body:
    def __init__(self, *, selected=True, texts=None):
        self.selected = selected
        self.texts = list(texts or [""])
        self.focused = False

    def focus(self):
        self.focused = True

    def evaluate(self, script, *args):
        if "selection.rangeCount" in script:
            return self.selected
        return None

    def inner_text(self, timeout=0):
        if len(self.texts) > 1:
            return self.texts.pop(0)
        return self.texts[0]


class Run298BodyRepairFinalTests(unittest.TestCase):
    def test_exact_range_clear_uses_backspace_and_requires_empty_body(self):
        page = _Page()
        body = _Body(selected=True, texts=[""])
        remaining = repair._clear_exact_body(page, body)
        self.assertTrue(body.focused)
        self.assertEqual(page.keyboard.presses, ["Backspace"])
        self.assertEqual(remaining, 0)

    def test_clear_fails_when_range_selection_is_not_established(self):
        page = _Page()
        body = _Body(selected=False, texts=[""])
        with self.assertRaises(repair.Run298BodyRepairError):
            repair._clear_exact_body(page, body)
        self.assertEqual(page.keyboard.presses, [])

    def test_clear_fails_when_old_body_remains(self):
        page = _Page()
        body = _Body(selected=True, texts=["x" * 25])
        with self.assertRaises(repair.Run298BodyRepairError):
            repair._clear_exact_body(page, body)
        self.assertEqual(page.keyboard.presses, ["Backspace"])

    def test_paste_requires_strict_pre_save_rendered_audit(self):
        page = _Page()
        body = _Body(selected=True, texts=["", "canonical"])
        metrics = {
            "expected_contained_in_actual": True,
            "visible_length_ratio": 1.0,
        }
        with patch.object(repair.note_base, "_markdown_to_safe_html", return_value="<p>canonical</p>"), \
             patch.object(repair.audit292, "_body_text_metrics", return_value=metrics):
            result = repair._paste_after_proven_clear(page, body, "canonical markdown", "title")
        self.assertEqual(result["remaining_chars_after_clear"], 0)
        self.assertEqual(result["visible_length_ratio"], 1.0)

    def test_repair_does_not_touch_header_upload_path(self):
        source = inspect.getsource(repair)
        self.assertNotIn("_upload_header_image(", source)
        self.assertNotIn("_download_eyecatch(", source)
        self.assertNotIn("https://note.com/new", source)
        self.assertNotIn("_create_browser_draft(", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("client.models", source)

    def test_repair_requires_strict_post_save_ratio(self):
        source = inspect.getsource(repair.repair)
        self.assertIn("0.82 <= final_ratio <= 1.15", source)
        self.assertIn("expected_contained_in_actual", source)
        self.assertIn("header_persisted_unchanged_during_body_repair", source)


if __name__ == "__main__":
    unittest.main()
