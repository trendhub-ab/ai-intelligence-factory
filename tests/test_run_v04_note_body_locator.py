"""Offline fail-closed selector tests: never read private note body text."""
from __future__ import annotations

import inspect
from pathlib import Path
import unittest

import note_draft_automation as base
import run_v04_note_body_locator as locator


class FakeElement:
    def __init__(self, *, x=200, y=400, width=680, height=160,
                 tag="div", editable="true", attrs=None, visible=True, nested=False):
        self.box = {"x": x, "y": y, "width": width, "height": height}
        self.tag = tag
        self.attrs = {"contenteditable": editable, **(attrs or {})}
        self.visible = visible
        self.nested = nested

    def is_visible(self, **_):
        return self.visible

    def bounding_box(self):
        return self.box

    def get_attribute(self, key):
        return self.attrs.get(key)

    def evaluate(self, script):
        if "tagName.toLowerCase()" in script:
            return self.tag
        if "querySelector" in script:
            return self.nested
        raise AssertionError("Unexpected DOM observation; private text access forbidden")


class FakeTitle:
    def __init__(self, y=300, height=80):
        self.box = {"x": 200, "y": y, "width": 600, "height": height}

    def bounding_box(self):
        return self.box


class FakeLocator:
    def __init__(self, elements):
        self.elements = elements

    def count(self):
        return len(self.elements)

    def nth(self, index):
        return self.elements[index]


class FakePage:
    def __init__(self, elements=(), *, url="https://editor.note.com/notes/new",
                 delayed=None):
        self.url = url
        self.elements = list(elements)
        self.delayed = delayed
        self.waits = 0
        self.seen_selectors = []

    def locator(self, selector):
        self.seen_selectors.append(selector)
        return FakeLocator(self.elements)

    def wait_for_timeout(self, ms):
        self.waits += 1
        if self.delayed is not None:
            self.elements = list(self.delayed)
            self.delayed = None


class V04NoteBodyLocatorTests(unittest.TestCase):
    def test_one_generic_body_below_title_is_accepted(self):
        body = FakeElement()
        page = FakePage([FakeElement(y=300, attrs={"class": "title"}), body])
        self.assertIs(locator.find_body(page, FakeTitle()), body)
        self.assertTrue(all("contenteditable" in query for query in page.seen_selectors))

    def test_semantic_body_wins_over_second_generic_editable(self):
        body = FakeElement(y=500, attrs={"data-placeholder": "本文を入力"})
        page = FakePage([FakeElement(y=420), body])
        self.assertIs(locator.find_body(page, FakeTitle()), body)

    def test_title_control_is_not_an_acceptable_body(self):
        page = FakePage([FakeElement(y=400, attrs={"aria-label": "記事タイトル"})])
        with self.assertRaisesRegex(base.NoteDraftError, "EDITOR_NOT_FOUND"):
            locator.find_body(page, FakeTitle())

    def test_ambiguous_generic_editables_fail_closed(self):
        page = FakePage([FakeElement(y=400), FakeElement(y=560)])
        with self.assertRaisesRegex(base.NoteDraftError, "EDITOR_AMBIGUOUS"):
            locator.find_body(page, FakeTitle())

    def test_hidden_nested_above_and_noneditable_controls_are_ignored(self):
        chosen = FakeElement(y=540)
        page = FakePage([
            FakeElement(y=400, visible=False),
            FakeElement(y=400, nested=True),
            FakeElement(y=380, height=20),
            FakeElement(y=400, editable="false"),
            chosen,
        ])
        self.assertIs(locator.find_body(page, FakeTitle()), chosen)

    def test_editor_mount_after_delay_can_resolve_without_writes(self):
        body = FakeElement()
        page = FakePage([], delayed=[body])
        self.assertIs(locator.find_body(page, FakeTitle()), body)
        self.assertEqual(page.waits, 1)

    def test_route_must_remain_note_editor_not_homepage_or_external(self):
        for url in ("https://note.com/", "https://evil.test/notes/new",
                    "https://note.com/notes"):
            with self.subTest(url=url):
                with self.assertRaisesRegex(base.NoteDraftError, "ROUTE_UNVERIFIED"):
                    locator.find_body(FakePage([FakeElement()], url=url), FakeTitle())

    def test_unverified_title_geometry_fail_closed(self):
        with self.assertRaisesRegex(base.NoteDraftError, "TITLE_GEOMETRY_INVALID"):
            locator.find_body(FakePage([FakeElement()]), None)

    def test_no_private_text_or_write_actions_in_locator(self):
        source = inspect.getsource(locator)
        for unsafe in ("inner_text(", "text_content(", "outerHTML", "innerHTML",
                       ".fill(", ".click(", "keyboard.press(", "fetch(", "screenshot(",
                       "console.log(", "page.goto("):
            self.assertNotIn(unsafe, source)
        self.assertIn("EDITOR_AMBIGUOUS", source)
        self.assertIn("EDITOR_NOT_FOUND", source)

    def test_bridged_browser_uses_body_locator_for_persistence_reopen(self):
        src = Path("run_v04_note_single_draft_bridge.py").read_text(encoding="utf-8")
        self.assertIn("base._find_body = body_locator.find_body", src)
        self.assertIn("V04_NOTE_STAGE=BODY_LOOKUP_BEGIN", src)
        self.assertIn("V04_NOTE_STAGE=BODY_LOCATED", src)
        self.assertIn("V04_NOTE_STAGE=BODY_PASTE_BEGIN", src)
        self.assertIn("V04_NOTE_STAGE=BODY_PASTE_RETURNED", src)
        self.assertIn("V04_NOTE_STAGE=BODY_RELOCATED", src)
        self.assertLess(src.index("BODY_LOOKUP_BEGIN"), src.index("BODY_PASTE_BEGIN"))
        self.assertLess(src.index("BODY_PASTE_BEGIN"), src.index("BODY_VERIFIED"))


if __name__ == "__main__":
    unittest.main()
