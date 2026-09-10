#!/usr/bin/env python3
"""Run334: repair the Run333 pre-save plan snapshot without changing its mutation contract.

Run333 live execution failed before any fill/save because a Playwright Locator was passed as the
argument to page.evaluate(), which JavaScript received as undefined. Run334 replaces only that
snapshot implementation with Locator.evaluate(), so the exact textarea element is the JavaScript
root. All Run333 business-state checks, copy, exact-one-final-click rule, public verification,
idempotency, and zero-model/zero-Notion boundaries remain unchanged.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run333_membership_description_exact_update as run333

CONFIRM_TOKEN = "UPDATE_MEMBERSHIP_DESCRIPTION_AI_DECISION_INTELLIGENCE_RUN334_EXACT"
RESULT_ENV = "NOTE_MEMBERSHIP_DESCRIPTION_RUN334_RESULT_FILE"


def _other_plan_snapshot(page: Any, description: Any) -> dict[str, Any]:
    """Snapshot the exact description-owning form from the Locator itself.

    `page` remains in the signature so this is a drop-in replacement for Run333, but the Locator
    executes the JavaScript and supplies its own DOM element as `descriptionEl`.
    """
    del page
    value = description.evaluate(
        r"""
        (descriptionEl) => {
          const form = descriptionEl.closest('form');
          if (!form) return null;
          const controls = [];
          const counts = {};
          for (const el of Array.from(form.querySelectorAll('input,textarea,select'))) {
            if (el === descriptionEl) continue;
            if (el.getAttribute('type') === 'file') continue;
            const row = {
              tag: el.tagName.toLowerCase(),
              type: el.getAttribute('type') || '',
              role: el.getAttribute('role') || '',
              name: el.getAttribute('name') || '',
              ariaLabel: el.getAttribute('aria-label') || '',
              value: 'value' in el ? String(el.value || '') : '',
              checked: 'checked' in el ? Boolean(el.checked) : null,
            };
            const base = [row.tag,row.type,row.role,row.name,row.ariaLabel].join('|');
            row.occurrence = counts[base] || 0;
            counts[base] = row.occurrence + 1;
            controls.push(row);
          }
          controls.sort((a,b) => JSON.stringify([
            a.tag,a.type,a.role,a.name,a.ariaLabel,a.occurrence
          ]).localeCompare(JSON.stringify([
            b.tag,b.type,b.role,b.name,b.ariaLabel,b.occurrence
          ])));
          const benefitLabels = Array.from(form.querySelectorAll('button[aria-label]'))
            .map(el => el.getAttribute('aria-label') || '')
            .filter(s => s.startsWith('特典を削除:'))
            .sort();
          return {controls, benefitLabels};
        }
        """
    )
    if not isinstance(value, dict):
        raise base.NoteDraftError("Run334 could not snapshot the exact target plan form")
    return value


def update() -> dict[str, Any]:
    if os.environ.get("NOTE_MEMBERSHIP_DESCRIPTION_RUN334_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run334 exact maintenance confirmation token is missing or invalid")

    # Run333 remains the complete audited mutation contract. Patch only the function that failed
    # before mutation, then satisfy Run333's inner hard-bound token locally.
    original_snapshot = run333._other_plan_snapshot
    original_inner_confirm = os.environ.get("NOTE_MEMBERSHIP_DESCRIPTION_RUN333_CONFIRM")
    run333._other_plan_snapshot = _other_plan_snapshot
    os.environ["NOTE_MEMBERSHIP_DESCRIPTION_RUN333_CONFIRM"] = run333.CONFIRM_TOKEN
    try:
        result = run333.update()
    finally:
        run333._other_plan_snapshot = original_snapshot
        if original_inner_confirm is None:
            os.environ.pop("NOTE_MEMBERSHIP_DESCRIPTION_RUN333_CONFIRM", None)
        else:
            os.environ["NOTE_MEMBERSHIP_DESCRIPTION_RUN333_CONFIRM"] = original_inner_confirm

    result = dict(result)
    result["run334_snapshot_repair"] = True
    return result


def main() -> None:
    result = update()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN334_MEMBERSHIP_DESCRIPTION_EXACT_UPDATE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
