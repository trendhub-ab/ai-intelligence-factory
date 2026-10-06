from __future__ import annotations

import note_draft_automation as note
import run222_note_presentation_integrity as header


class _Button:
    def __init__(self, name: str):
        self.name = name
        self.clicked = False

    def is_visible(self, timeout=0):
        return True

    def click(self):
        self.clicked = True


class _Locator:
    def __init__(self, buttons):
        self.buttons = list(buttons)

    def count(self):
        return len(self.buttons)

    def nth(self, index):
        return self.buttons[index]


class _Page:
    def __init__(self, *, labeled=None, geometry_index=-1, all_buttons=None):
        self.labeled = list(labeled or [])
        self.geometry_index = geometry_index
        self.all_buttons = list(all_buttons or [])
        self.waits = []
        self.evaluate_calls = []

    def locator(self, selector):
        if selector == "button":
            return _Locator(self.all_buttons)
        return _Locator(self.labeled)

    def evaluate(self, script):
        self.evaluate_calls.append(script)
        if "matches" in script:
            return self.geometry_index
        return None

    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)


def test_header_button_prefers_existing_semantic_selector():
    semantic = _Button("semantic")
    page = _Page(labeled=[semantic], geometry_index=0, all_buttons=[_Button("geometry")])
    found = header.find_header_image_add_button(note, page)
    assert found is semantic
    assert page.evaluate_calls == []


def test_header_button_falls_back_to_unique_unlabeled_geometry_candidate():
    geometry = _Button("geometry")
    page = _Page(geometry_index=0, all_buttons=[geometry])
    found = header.find_header_image_add_button(note, page)
    assert found is geometry
    assert page.waits == [1500]
    source = "\n".join(page.evaluate_calls)
    assert "aria-label" in source
    assert "innerText" in source
    assert "r.width >= 30" in source
    assert "r.width <= 56" in source
    assert "r.y > 60" in source
    assert "r.y < 220" in source
    assert "r.x > 400" in source
    assert "matches.length === 1" in source


def test_header_button_geometry_fallback_fails_closed_when_no_unique_candidate():
    page = _Page(geometry_index=-1, all_buttons=[_Button("other")])
    assert header.find_header_image_add_button(note, page) is None
