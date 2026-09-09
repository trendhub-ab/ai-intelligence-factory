#!/usr/bin/env python3
"""Run315-only DOM Range adapter for replacing the legacy onboarding body.

The generic note paste helper uses keyboard Control+A, which is safe for new/empty drafts but
can fail to select an entire populated note editor. Run315 targets one audited existing article,
so this adapter scopes the selection to the exact body contenteditable with a DOM Range, deletes
that exact selection, verifies the body is empty, and only then dispatches the same safe
HTML/plain-text paste payload used by the shared helper.

This module changes no global repository behavior: the override exists only inside the Run315
process that imports and installs it.
"""
from __future__ import annotations

from typing import Any

import note_draft_automation as base
import run315_member_onboarding_update as run315


def _select_exact_body_range(body: Any) -> dict[str, Any]:
    return body.evaluate(
        """el => {
          if (!(el instanceof HTMLElement) || !el.isContentEditable) {
            return {ok:false, reason:'target_not_contenteditable'};
          }

          el.focus();
          const selection = window.getSelection();
          if (!selection) return {ok:false, reason:'selection_unavailable'};

          const range = document.createRange();
          range.selectNodeContents(el);
          selection.removeAllRanges();
          selection.addRange(range);

          if (selection.rangeCount !== 1) {
            return {ok:false, reason:'unexpected_range_count', rangeCount:selection.rangeCount};
          }
          const selected = selection.getRangeAt(0);
          const exact = (
            selected.startContainer === el &&
            selected.startOffset === 0 &&
            selected.endContainer === el &&
            selected.endOffset === el.childNodes.length
          );
          if (!exact) {
            return {
              ok:false,
              reason:'range_not_exact_body',
              startOffset:selected.startOffset,
              endOffset:selected.endOffset,
              childCount:el.childNodes.length,
            };
          }
          return {
            ok:true,
            childCount:el.childNodes.length,
            beforeTextLength:String(el.innerText || '').length,
          };
        }"""
    )


def _normalized_body_text(body: Any) -> str:
    text = str(body.inner_text(timeout=10000) or "")
    return text.replace("\u200b", "").replace("\ufeff", "").strip()


def _paste_manuscript_dom_range(page: Any, body: Any, manuscript: str) -> None:
    """Delete exactly the selected body, prove it is empty, then paste the authorized copy."""
    safe_html = base._markdown_to_safe_html(manuscript)
    state = _select_exact_body_range(body)
    if not isinstance(state, dict) or state.get("ok") is not True:
        reason = state.get("reason") if isinstance(state, dict) else "invalid_selection_state"
        raise base.NoteDraftError(f"Run315 DOM Range body selection failed: {reason}")

    # A synthetic ClipboardEvent alone does not guarantee that note deletes the selected legacy
    # blocks. Use a real keyboard deletion only after the DOM Range has been proven to cover the
    # exact body contents. This is the key distinction from the unsafe generic Control+A path.
    page.keyboard.press("Backspace")
    page.wait_for_timeout(350)
    residual = _normalized_body_text(body)
    if residual:
        raise base.NoteDraftError(
            f"Run315 exact body deletion left residual text ({len(residual)} chars)"
        )

    body.evaluate(
        """(el, payload) => {
          el.focus();
          const data = new DataTransfer();
          data.setData('text/html', payload.html);
          data.setData('text/plain', payload.text);
          const event = new ClipboardEvent('paste', {
            bubbles:true,
            cancelable:true,
            clipboardData:data,
          });
          el.dispatchEvent(event);
        }""",
        {"html": safe_html, "text": manuscript},
    )
    page.wait_for_timeout(1200)


def install_run315_dom_range_replacer() -> None:
    """Override the shared paste hook only for this Run315 process."""
    base._paste_manuscript = _paste_manuscript_dom_range


def main() -> None:
    install_run315_dom_range_replacer()
    run315.main()


if __name__ == "__main__":
    main()
