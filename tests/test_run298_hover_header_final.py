from __future__ import annotations

import inspect
import unittest

import run298_hover_header_final as final


class _Mouse:
    def move(self, *args, **kwargs):
        return None


class _Control:
    def __init__(self, box, *, aria="", title="", text=""):
        self._box = box
        self._aria = aria
        self._title = title
        self._text = text

    def is_visible(self, timeout=0):
        return True

    def bounding_box(self):
        return dict(self._box)

    def get_attribute(self, key):
        if key == "aria-label":
            return self._aria
        if key == "title":
            return self._title
        if key == "data-testid":
            return ""
        return ""

    def inner_text(self, timeout=0):
        return self._text


class _Locator:
    def __init__(self, items):
        self.items = list(items)

    def count(self):
        return len(self.items)

    def nth(self, index):
        return self.items[index]


class _Header:
    def hover(self, timeout=0):
        return None


class _Page:
    def __init__(self, controls):
        self.controls = controls
        self.mouse = _Mouse()

    def wait_for_timeout(self, ms):
        return None

    def locator(self, selector):
        return _Locator(self.controls)


class Run298HoverHeaderFinalTests(unittest.TestCase):
    def test_unique_upper_right_remove_control_is_selected(self):
        box = {"x": 100.0, "y": 80.0, "width": 620.0, "height": 325.0}
        page = _Page([
            _Control({"x": 688.0, "y": 90.0, "width": 28.0, "height": 28.0}, aria="画像を削除"),
            _Control({"x": 20.0, "y": 20.0, "width": 40.0, "height": 40.0}, aria="別の操作"),
        ])
        control, count, strong = final._hover_remove_control(page, _Header(), box)
        self.assertIs(control, page.controls[0])
        self.assertEqual(count, 1)
        self.assertTrue(strong)

    def test_unsafe_save_control_is_rejected_even_in_header_corner(self):
        box = {"x": 100.0, "y": 80.0, "width": 620.0, "height": 325.0}
        page = _Page([
            _Control({"x": 688.0, "y": 90.0, "width": 28.0, "height": 28.0}, aria="保存"),
        ])
        with self.assertRaises(final.Run298HoverHeaderError):
            final._hover_remove_control(page, _Header(), box)

    def test_multiple_strong_header_controls_fail_closed(self):
        box = {"x": 100.0, "y": 80.0, "width": 620.0, "height": 325.0}
        page = _Page([
            _Control({"x": 680.0, "y": 90.0, "width": 24.0, "height": 24.0}, aria="画像を削除"),
            _Control({"x": 650.0, "y": 90.0, "width": 24.0, "height": 24.0}, aria="見出し画像"),
        ])
        with self.assertRaises(final.Run298HoverHeaderError):
            final._hover_remove_control(page, _Header(), box)

    def test_header_replacement_precedes_manuscript_mutation(self):
        source = inspect.getsource(final.refresh)
        self.assertLess(source.index("_replace_existing_header"), source.index("_paste_manuscript"))

    def test_no_new_draft_or_model_surface(self):
        source = inspect.getsource(final)
        self.assertNotIn("https://note.com/new", source)
        self.assertNotIn("_create_browser_draft(", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("client.models", source)


if __name__ == "__main__":
    unittest.main()
