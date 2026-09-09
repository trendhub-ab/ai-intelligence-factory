from __future__ import annotations

import inspect
import unittest

import note_draft_automation as base
import run315_member_onboarding_update as run315
import run315_member_onboarding_update_dom_range as dom_range


class Run315DomRangeReplaceTests(unittest.TestCase):
    def test_replacer_selects_exact_body_with_dom_range(self) -> None:
        source = inspect.getsource(dom_range._paste_manuscript_dom_range)
        self.assertIn("document.createRange()", source)
        self.assertIn("range.selectNodeContents(el)", source)
        self.assertIn("selection.removeAllRanges()", source)
        self.assertIn("selection.addRange(range)", source)
        self.assertIn("selected.startContainer === el", source)
        self.assertIn("selected.endContainer === el", source)
        self.assertIn("selected.endOffset === el.childNodes.length", source)
        self.assertNotIn("Control+A", source)

    def test_replacer_preserves_shared_safe_paste_payload(self) -> None:
        source = inspect.getsource(dom_range._paste_manuscript_dom_range)
        self.assertIn("base._markdown_to_safe_html(manuscript)", source)
        self.assertIn("new DataTransfer()", source)
        self.assertIn("text/html", source)
        self.assertIn("text/plain", source)
        self.assertIn("new ClipboardEvent('paste'", source)

    def test_installer_overrides_only_run315_process_hook(self) -> None:
        original = base._paste_manuscript
        try:
            dom_range.install_run315_dom_range_replacer()
            self.assertIs(base._paste_manuscript, dom_range._paste_manuscript_dom_range)
            self.assertIs(run315.base, base)
        finally:
            base._paste_manuscript = original

    def test_run315_update_still_uses_shared_paste_hook_and_fail_closed_verification(self) -> None:
        source = inspect.getsource(run315.update)
        self.assertIn("base._paste_manuscript(page, body, MANUSCRIPT)", source)
        self.assertIn("base._verify_body_content(body, MANUSCRIPT)", source)
        self.assertIn("_verify_editor(body)", source)
        self.assertIn("_sha256(current_body) != AUDITED_BODY_SHA256", source)


if __name__ == "__main__":
    unittest.main()
