#!/usr/bin/env python3
"""Run298 existing-header replacement overlay for the exact GenRec private draft.

Run193's official add-image control is correct for a draft without a header, but an already
populated private draft may not expose that add control. This overlay changes only the upload
step used by Run298:

- if no existing header fingerprint is present, keep Run193 unchanged;
- if a header already exists, require one unambiguous Run188 header-zone image file input;
- set the reviewed Run296 eyecatch through that input;
- complete only one safe crop/confirm control when a crop UI appears;
- require the visible header-media fingerprint to change before returning success.

No new draft, public release, model request, or non-UI posting API is introduced.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import note_draft_automation as note_base
import run188_note_header_upload_fallback as run188
import run193_note_official_header_upload as run193
import run298_genrec_inplace_refresh as run298


class ExistingHeaderReplaceError(note_base.NoteDraftError):
    pass


def _header_hash(page: Any) -> tuple[str, int]:
    title = note_base._find_title(page)
    return run298._header_media_fingerprint(page, title)


def _visible_crop_roots(page: Any) -> list[Any]:
    try:
        return [
            root
            for root in run193._visible_modal_roots(page)
            if run193._root_looks_crop_related(root)
        ]
    except Exception:
        return []


def _finish_crop_once(page: Any) -> bool:
    roots = _visible_crop_roots(page)
    if not roots:
        return False
    candidates: list[tuple[Any, Any]] = []
    for root in roots:
        for control in run193._safe_crop_candidates(root):
            candidates.append((root, control))
    if len(candidates) != 1:
        raise ExistingHeaderReplaceError(
            f"existing header crop controls ambiguous:{len(candidates)}"
        )
    root, control = candidates[0]
    try:
        control.click()
        try:
            root.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass
    except Exception as exc:
        raise ExistingHeaderReplaceError("existing header crop confirmation failed") from exc
    return True


def _wait_for_changed_header(page: Any, before_hash: str, seconds: float = 20.0) -> tuple[str, int]:
    deadline = time.time() + seconds
    crop_clicked = False
    while time.time() < deadline:
        roots = _visible_crop_roots(page)
        if roots and not crop_clicked:
            crop_clicked = _finish_crop_once(page)
        after_hash, after_count = _header_hash(page)
        if after_hash and after_count >= 1 and after_hash != before_hash and not _visible_crop_roots(page):
            return after_hash, after_count
        page.wait_for_timeout(300)
    raise ExistingHeaderReplaceError(
        f"existing header media did not change; crop_clicked={str(crop_clicked).lower()}"
    )


def _replace_existing_header(page: Any, image_path: Path) -> None:
    before_hash, before_count = _header_hash(page)
    if not before_hash or before_count < 1:
        raise ExistingHeaderReplaceError("existing header fingerprint missing before replacement")

    file_input, image_input_count = run188._safe_header_file_input(page)
    if file_input is None:
        raise ExistingHeaderReplaceError(
            f"existing header has no unambiguous safe image input:{image_input_count}"
        )
    try:
        file_input.set_input_files(str(image_path))
    except Exception as exc:
        raise ExistingHeaderReplaceError("existing header image input rejected eyecatch") from exc
    page.wait_for_timeout(700)
    _wait_for_changed_header(page, before_hash)


def _header_aware_upload(page: Any, image_path: Path) -> None:
    before_hash, before_count = _header_hash(page)
    if before_hash and before_count >= 1:
        _replace_existing_header(page, image_path)
        return
    run193._upload_header_image(page, image_path)


def install() -> None:
    original_install = run298.official_header.install

    def install_for_run298() -> None:
        original_install()
        run298.note_base._upload_header_image = _header_aware_upload

    run298.official_header.install = install_for_run298


def main() -> int:
    install()
    return run298.main()


if __name__ == "__main__":
    raise SystemExit(main())