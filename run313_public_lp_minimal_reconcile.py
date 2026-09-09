#!/usr/bin/env python3
"""Run313: minimally reconcile the hand-edited fixed public note LP.

This is intentionally NOT a full-body publisher. It is bound to one audited editor snapshot
(body SHA-256) and performs exactly two text edits:
1) delete a malformed duplicated legacy prefix;
2) correct the mobile-support wording to the current PC-first member UX contract.

The user's hand-edited formatting and all unrelated copy remain authoritative.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import run310_public_lp_update as run310

CONFIRM_TOKEN = "RECONCILE_PUBLIC_LP_NED673E381EF8_SHA3E356937"
RESULT_ENV = "NOTE_PUBLIC_LP_RECONCILE_RESULT_FILE"
EXPECTED_TITLE = "「このAI、使える！」を根拠付きで判断する｜Decision Brief + AI意思決定DB"
EXPECTED_BODY_SHA256 = "3e3569378f388634c02d107d11672dd05958bbee4c4b4a6c9a2368af415f4b5c"

LEGACY_PREFIX_START = "そんな人のために作りました。"
LEGACY_PREFIX_END = "AIやITの大量の情報から、「これは知っておいた"
CANONICAL_BODY_START = "「このAI、使える！」を、根拠付きで判断できる。"
MOBILE_OLD = "PC・スマートフォン対応"
MOBILE_NEW = "PCでの利用を推奨（スマートフォン向け簡易ビューあり）"

REQUIRED_MARKERS = (
    CANONICAL_BODY_START,
    "Decision Brief",
    "AI意思決定DB",
    "OfficialVendor",
    "月額1,980円",
    "使う・試す・待つ・避ける",
)


def _body_text(body: Any) -> str:
    try:
        return str(body.inner_text(timeout=10000) or "").strip()
    except Exception as exc:
        raise base.NoteDraftError("Run313 could not read the exact note body") from exc


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _select_exact_block_range(body: Any, start_text: str, end_text: str) -> None:
    result = body.evaluate(
        """
        (root, args) => {
          const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
          const candidates = Array.from(root.querySelectorAll('p,h1,h2,h3,h4,h5,h6,li,blockquote,div'));
          const unique = (text) => {
            const wanted = norm(text);
            const matches = candidates.filter((el) => norm(el.innerText) === wanted);
            // Prefer the smallest exact text-bearing element, avoiding nested duplicate wrappers.
            const leaf = matches.filter((el) => !matches.some((other) => other !== el && el.contains(other)));
            const usable = leaf.length ? leaf : matches;
            if (usable.length !== 1) return {error: `expected 1 exact block for ${wanted}; got ${usable.length}`};
            return {element: usable[0]};
          };
          const start = unique(args.start);
          if (start.error) return {error: start.error};
          const end = unique(args.end);
          if (end.error) return {error: end.error};
          if (!(start.element.compareDocumentPosition(end.element) & Node.DOCUMENT_POSITION_FOLLOWING)) {
            return {error: 'legacy prefix end is not after prefix start'};
          }
          const range = document.createRange();
          range.setStartBefore(start.element);
          range.setEndAfter(end.element);
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          root.focus();
          return {ok: true};
        }
        """,
        {"start": start_text, "end": end_text},
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise base.NoteDraftError(f"Run313 could not select exact malformed prefix: {result}")


def _select_exact_block_text(body: Any, text: str) -> None:
    result = body.evaluate(
        """
        (root, text) => {
          const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim();
          const wanted = norm(text);
          const candidates = Array.from(root.querySelectorAll('p,h1,h2,h3,h4,h5,h6,li,blockquote,div'));
          const matches = candidates.filter((el) => norm(el.innerText) === wanted);
          const leaf = matches.filter((el) => !matches.some((other) => other !== el && el.contains(other)));
          const usable = leaf.length ? leaf : matches;
          if (usable.length !== 1) return {error: `expected 1 exact block for ${wanted}; got ${usable.length}`};
          const range = document.createRange();
          range.selectNodeContents(usable[0]);
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          root.focus();
          return {ok: true};
        }
        """,
        text,
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise base.NoteDraftError(f"Run313 could not select exact mobile-support block: {result}")


def _validate_reconciled_editor(body: Any, original_text: str) -> str:
    current = _body_text(body)
    expected = original_text[original_text.index(CANONICAL_BODY_START):]
    expected = expected.replace(MOBILE_OLD, MOBILE_NEW, 1).strip()
    if current != expected:
        raise base.NoteDraftError("Run313 editor body differs from the exact two-edit expected result")
    if LEGACY_PREFIX_START in current or LEGACY_PREFIX_END in current or MOBILE_OLD in current:
        raise base.NoteDraftError("Run313 legacy/misleading copy remains after editor reconciliation")
    for marker in REQUIRED_MARKERS + (MOBILE_NEW,):
        if marker not in current:
            raise base.NoteDraftError(f"Run313 reconciled editor is missing marker: {marker}")
    links = body.locator('a[href*="note.com/trendhub_biz/membership"]')
    if links.count() < 1:
        raise base.NoteDraftError("Run313 membership CTA link disappeared during minimal edit")
    return current


def _verify_public(page: Any) -> dict[str, Any]:
    page.goto(run310.TARGET_PUBLIC_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1600)
    text = " ".join(run310._article_text(page).split())
    if EXPECTED_TITLE not in text:
        full = " ".join(str(page.locator("body").inner_text(timeout=10000) or "").split())
        if EXPECTED_TITLE not in full:
            raise base.NoteDraftError("Run313 public verification could not find the current title")
        text = full
    for marker in REQUIRED_MARKERS + (MOBILE_NEW,):
        if " ".join(marker.split()) not in text:
            raise base.NoteDraftError(f"Run313 public verification missing marker: {marker}")
    for forbidden in (LEGACY_PREFIX_START, LEGACY_PREFIX_END, MOBILE_OLD):
        if " ".join(forbidden.split()) in text:
            raise base.NoteDraftError(f"Run313 public verification still contains: {forbidden}")
    if page.locator('a[href*="note.com/trendhub_biz/membership"]').count() < 1:
        raise base.NoteDraftError("Run313 public membership CTA link verification failed")
    return {
        "public_url": run310.TARGET_PUBLIC_URL,
        "membership_link_verified": True,
        "pc_first_copy_verified": True,
        "malformed_prefix_removed": True,
    }


def reconcile() -> dict[str, Any]:
    if os.environ.get("NOTE_PUBLIC_LP_RECONCILE_CONFIRM", "").strip() != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run313 exact-state reconciliation confirmation is missing or invalid")

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
    except ImportError as exc:
        raise base.NoteDraftError("Playwright is required for Run313") from exc

    with sync_playwright() as playwright:
        context = run310.cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            run310._open_exact_editor(context, page)
            title_field = base._find_title(page)
            if run310._field_text(title_field) != EXPECTED_TITLE:
                raise base.NoteDraftError("Run313 refuses an unexpected fixed-LP title")
            body = base._find_body(page, title_field)
            original_text = _body_text(body)
            if _sha256(original_text) != EXPECTED_BODY_SHA256:
                # Idempotent path: if the two corrections are already live, verify without mutation.
                if (
                    original_text.startswith(CANONICAL_BODY_START)
                    and LEGACY_PREFIX_START not in original_text
                    and LEGACY_PREFIX_END not in original_text
                    and MOBILE_OLD not in original_text
                    and MOBILE_NEW in original_text
                ):
                    verification = _verify_public(page)
                    return {
                        "status": "already_reconciled",
                        "target_note_id": run310.TARGET_NOTE_ID,
                        "public_mutation": False,
                        "zero_gemini_calls": True,
                        "title": EXPECTED_TITLE,
                        **verification,
                    }
                raise base.NoteDraftError(
                    "Run313 refuses body drift: live editor no longer matches the audited SHA-256 snapshot"
                )

            if not original_text.startswith(LEGACY_PREFIX_START):
                raise base.NoteDraftError("Run313 audited malformed prefix is not at the body start")
            if original_text.count(LEGACY_PREFIX_END) != 1 or original_text.count(MOBILE_OLD) != 1:
                raise base.NoteDraftError("Run313 expected correction targets are not unique")
            if CANONICAL_BODY_START not in original_text:
                raise base.NoteDraftError("Run313 canonical body start is missing")

            _select_exact_block_range(body, LEGACY_PREFIX_START, LEGACY_PREFIX_END)
            page.keyboard.press("Backspace")
            page.wait_for_timeout(500)

            _select_exact_block_text(body, MOBILE_OLD)
            page.keyboard.insert_text(MOBILE_NEW)
            page.wait_for_timeout(900)

            reconciled_text = _validate_reconciled_editor(body, original_text)
            reconciled_sha = _sha256(reconciled_text)
            page.wait_for_timeout(1400)

            run310._unique_button(page, "公開に進む").click()
            try:
                page.wait_for_url(f"**/notes/{run310.TARGET_NOTE_ID}/publish/**", timeout=15000)
            except PlaywrightTimeoutError as exc:
                raise base.NoteDraftError("Run313 did not reach the exact publish settings route") from exc
            if not str(page.url or "").startswith(run310.TARGET_PUBLISH_URL):
                raise base.NoteDraftError("Run313 publish settings route is not the exact fixed LP")
            page.wait_for_timeout(1000)
            run310._unique_button(page, "更新する").click()
            page.wait_for_timeout(2200)

            verification = _verify_public(page)
            return {
                "status": "reconciled_and_verified",
                "target_note_id": run310.TARGET_NOTE_ID,
                "public_mutation": True,
                "zero_gemini_calls": True,
                "title": EXPECTED_TITLE,
                "source_body_sha256": EXPECTED_BODY_SHA256,
                "reconciled_body_sha256": reconciled_sha,
                **verification,
            }
        finally:
            context.close()


def main() -> None:
    result = reconcile()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN313_PUBLIC_LP_RECONCILE=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
