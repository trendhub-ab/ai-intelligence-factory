from __future__ import annotations

import note_draft_automation as draft


class _Keyboard:
    def __init__(self) -> None:
        self.presses: list[str] = []

    def press(self, key: str) -> None:
        self.presses.append(key)


class _Context:
    def __init__(self) -> None:
        self.grants: list[tuple[tuple[str, ...], str | None]] = []

    def grant_permissions(self, permissions, origin=None) -> None:
        self.grants.append((tuple(permissions), origin))


class _Page:
    def __init__(self) -> None:
        self.url = "https://note.com/notes/private/edit"
        self.context = _Context()
        self.keyboard = _Keyboard()
        self.evaluate_calls: list[tuple[str, object | None]] = []
        self.waits: list[int] = []

    def evaluate(self, script: str, arg=None):
        self.evaluate_calls.append((script, arg))
        return True

    def wait_for_timeout(self, milliseconds: int) -> None:
        self.waits.append(milliseconds)


class _Body:
    def __init__(self) -> None:
        self.clicks = 0
        self.evaluate_calls: list[tuple[str, object | None]] = []

    def click(self) -> None:
        self.clicks += 1

    def inner_text(self, timeout: int = 0) -> str:
        return ""

    def evaluate(self, script: str, arg=None):
        self.evaluate_calls.append((script, arg))
        return True


def test_paste_manuscript_uses_browser_clipboard_and_trusted_keyboard_paste() -> None:
    page = _Page()
    body = _Body()

    draft._paste_manuscript(page, body, "## Heading\n\nBody **bold**")

    assert page.context.grants == [
        (("clipboard-read", "clipboard-write"), "https://note.com")
    ]
    assert any(
        "navigator.clipboard.write" in script and "ClipboardItem" in script
        for script, _ in page.evaluate_calls
    )
    assert "Control+V" in page.keyboard.presses
    assert not any("ClipboardEvent" in script for script, _ in body.evaluate_calls)
