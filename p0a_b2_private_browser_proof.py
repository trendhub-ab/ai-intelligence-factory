#!/usr/bin/env python3
"""One-shot real-browser proof for P0-A canonical persistence + B2 stable draft identity.

This proof is intentionally isolated from production Notion queues. It creates exactly one
private note draft containing synthetic, non-sensitive fixture text, verifies the canonical
body before save, saves and reopens it, derives the stable private draft identity from the
edit URL, reconstructs the canonical private edit route, reopens that route, and verifies the
same title/body canonically again.

The fixture deliberately excludes inline code because real-browser evidence on 2026-10-04
proved that note's HTML paste path flattens it. Production now rejects inline code before
browser mutation until a preserving note path is proven. Fenced code remains in this proof.

No model calls. No Notion reads/writes. No public release action. No private URL/identity/body
is printed or written to the result receipt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import note_draft_automation as base
import note_publication_reconcile as lifecycle
import run187_note_editor_readiness as run187
import run190_note_persistent_cloud as cloud
import run222_note_presentation_integrity as run222
import run417_note_body_verification as run417


FIXTURE_TITLE = "AIIF P0-A/B2 private browser proof"
FIXTURE_SOURCE = """## Canonical browser proof

この下書きはP0-A/B2の非公開ブラウザ実証専用です。数値は10秒、対象はProduct Aです。

- 否定・数値・単位・固有名を全文一致で検証する
- 保存後に再openしてDOMからcanonical documentを再構成する

1. save
2. reopen
3. compare

リンク: [OpenAI](https://openai.com/)

> private draft only

```python
x = 1
print("proof")
```

---

### Result boundary

公開操作は行いません。
"""


class ProofError(RuntimeError):
    pass


def _title_value(field: Any) -> str:
    tag = str(field.evaluate("el => el.tagName.toLowerCase()"))
    if tag in {"input", "textarea"}:
        return str(field.input_value() or "").strip()
    return str(field.inner_text() or "").strip()


def _write_result(result: dict[str, object]) -> None:
    target = os.environ.get("P0A_B2_PROOF_RESULT_FILE", "").strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> dict[str, object]:
    cloud.install()
    lifecycle.install_draft_identity(base)

    if base._verify_body_content is not run417.verify_body_content:
        raise ProofError("canonical verifier is not active")
    if base._markdown_to_safe_html is not run417.markdown_to_safe_html:
        raise ProofError("canonical renderer is not active")
    if getattr(base, "_p0b2_identity_installed", False) is not True:
        raise ProofError("stable draft identity guard is not active")

    manuscript = run222.prepare_note_editor_manuscript(FIXTURE_SOURCE, FIXTURE_TITLE)
    if "```python" in manuscript:
        raise ProofError("presentation transform did not remove fence language metadata")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ProofError("Playwright is required") from exc

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        pages = list(context.pages)
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)
            cloud._establish_editor(page, context)
            if not run187._is_editor_url(str(page.url or "")):
                raise ProofError("private editor route was not established")

            title_field = base._set_title(page, FIXTURE_TITLE)
            body = base._find_body(page, title_field)
            base._paste_manuscript(page, body, manuscript)
            body = base._find_body(page, title_field)
            base._verify_body_content(body, manuscript)

            draft_url = base._save_draft_and_verify(
                page, FIXTURE_TITLE, manuscript, image_required=False
            )
            identity = lifecycle.draft_identity_from_url(
                draft_url, error_type=ProofError
            )
            if not identity:
                raise ProofError("stable private draft identity was not derived")

            canonical_edit_url = f"https://note.com/notes/{identity}/edit"
            if lifecycle.draft_identity_from_url(canonical_edit_url, error_type=ProofError) != identity:
                raise ProofError("stable identity route reconstruction failed")

            page.goto(canonical_edit_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)
            if base._looks_logged_out(page):
                raise ProofError("note session expired on stable-identity reopen")
            if not run187._is_editor_url(str(page.url or "")):
                raise ProofError("stable identity did not reopen a private editor route")

            persisted_title = _title_value(base._find_title(page))
            if persisted_title != FIXTURE_TITLE:
                raise ProofError("stable-identity reopen title mismatch")
            reopened_title_field = base._find_title(page)
            reopened_body = base._find_body(page, reopened_title_field)
            base._verify_body_content(reopened_body, manuscript)
        finally:
            context.close()

    result = {
        "status": "private_browser_proof_passed",
        "zero_gemini_calls": True,
        "notion_access": False,
        "public_release": False,
        "private_draft_created": True,
        "canonical_insert_match": True,
        "canonical_save_reopen_match": True,
        "stable_identity_observed": True,
        "stable_identity_reopen_match": True,
    }
    _write_result(result)
    return result


def main() -> None:
    result = run()
    # Content-free receipt only; never print the private URL, draft identity, title, or body.
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
