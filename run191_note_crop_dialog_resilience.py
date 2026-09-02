#!/usr/bin/env python3
"""Run191 overlay: complete note eyecatch crop dialogs without brittle first-dialog assumptions.

Live Run190 proved that header upload reaches note's crop UI, but Run188 inspected only the
first visible role=dialog and recognized only four Japanese completion labels. Current note UI
can mount multiple modal/portal layers, so the crop completion control may live in another
visible modal.

Safety contract:
- zero Gemini/model calls;
- never clicks public-release/post controls;
- only clicks a visible, enabled crop-completion control with explicit positive semantics;
- searches all visible modal/dialog roots, not only the first one;
- fails closed with sanitized control diagnostics when no unique safe control exists.
"""
from __future__ import annotations

import time
from typing import Any

import note_draft_automation as base
import run185_note_ready_legacy_skip as run185
import run188_note_header_upload_fallback as run188
import run189_note_editor_route_gate as run189


_STRONG_POSITIVE_TERMS = (
    "保存",
    "完了",
    "決定",
    "適用",
    "確定",
    "save",
    "done",
    "apply",
    "confirm",
)
_SECONDARY_POSITIVE_TERMS = (
    "この画像を使用",
    "画像を使用",
    "使用する",
    "use image",
)
_REJECT_TERMS = (
    "公開",
    "投稿",
    "publish",
    "release",
    "キャンセル",
    "閉じる",
    "戻る",
    "削除",
    "取消",
    "リセット",
    "やめる",
    "remove",
    "delete",
    "cancel",
    "close",
    "back",
)


def _semantic_text(control: Any) -> str:
    parts: list[str] = []
    for getter in (
        lambda: control.inner_text(timeout=300),
        lambda: control.get_attribute("aria-label"),
        lambda: control.get_attribute("title"),
        lambda: control.get_attribute("data-testid"),
        lambda: control.get_attribute("name"),
        lambda: control.get_attribute("value"),
    ):
        try:
            value = getter()
        except Exception:
            value = None
        if value:
            parts.append(str(value).strip())
    return " ".join(parts).strip().lower()


def _completion_rank(text: str) -> int | None:
    normalized = (text or "").strip().lower()
    if not normalized or any(term in normalized for term in _REJECT_TERMS):
        return None
    if any(term in normalized for term in _STRONG_POSITIVE_TERMS):
        return 0
    if any(term in normalized for term in _SECONDARY_POSITIVE_TERMS):
        return 1
    return None


def _is_safe_completion_semantic(text: str) -> bool:
    return _completion_rank(text) is not None


def _visible_modal_roots(page: Any) -> list[Any]:
    roots: list[Any] = []
    locator = page.locator('[role="dialog"], [aria-modal="true"]')
    try:
        count = min(locator.count(), 20)
    except Exception:
        count = 0
    for index in range(count):
        root = locator.nth(index)
        try:
            if root.is_visible(timeout=250):
                roots.append(root)
        except Exception:
            continue
    return roots


def _safe_completion_candidates(root: Any) -> list[tuple[int, str, Any]]:
    candidates: list[tuple[int, str, Any]] = []
    controls = root.locator('button, [role="button"]')
    try:
        count = min(controls.count(), 40)
    except Exception:
        count = 0
    for index in range(count):
        control = controls.nth(index)
        try:
            if not control.is_visible(timeout=180) or not control.is_enabled():
                continue
        except Exception:
            continue
        semantic = _semantic_text(control)
        rank = _completion_rank(semantic)
        if rank is not None:
            candidates.append((rank, semantic, control))
    return candidates


def _control_diagnostics(page: Any) -> str:
    labels: list[str] = []
    roots = _visible_modal_roots(page)
    for root_index, root in enumerate(roots):
        controls = root.locator('button, [role="button"]')
        try:
            count = min(controls.count(), 16)
        except Exception:
            count = 0
        for index in range(count):
            control = controls.nth(index)
            try:
                if not control.is_visible(timeout=120):
                    continue
            except Exception:
                continue
            semantic = _semantic_text(control).replace("\n", " ")[:80]
            if semantic:
                labels.append(f"d{root_index}:{semantic}")
    joined = " | ".join(labels[:20])
    return f"visible_modals={len(roots)}; controls={joined or 'none'}"


def _finish_crop_dialog(page: Any) -> None:
    # The cropper may render after upload animation and may coexist with another visible
    # modal/portal. Wait briefly for the modal set to settle, then inspect all roots.
    deadline = time.time() + 12.0
    saw_modal = False
    while time.time() < deadline:
        roots = _visible_modal_roots(page)
        if not roots:
            page.wait_for_timeout(250)
            continue
        saw_modal = True

        ranked: list[tuple[int, int, str, Any, Any]] = []
        for root_index, root in enumerate(roots):
            for rank, semantic, control in _safe_completion_candidates(root):
                ranked.append((rank, root_index, semantic, control, root))

        if ranked:
            ranked.sort(key=lambda row: (row[0], row[1], row[2]))
            best_rank = ranked[0][0]
            best = [row for row in ranked if row[0] == best_rank]
            if len(best) != 1:
                raise base.NoteDraftError(
                    "note eyecatch crop dialog has multiple safe completion controls; "
                    + _control_diagnostics(page)
                )
            _, _, _, control, root = best[0]
            try:
                control.click()
            except Exception as exc:
                raise base.NoteDraftError("note eyecatch crop/save control could not be clicked") from exc

            # Some note builds keep a parent modal mounted while replacing only the crop
            # panel. Do not require the exact root to disappear; the existing Run188 header
            # preview verification remains the authoritative post-condition.
            try:
                root.wait_for(state="hidden", timeout=5000)
            except Exception:
                page.wait_for_timeout(500)
            return

        page.wait_for_timeout(350)

    if not saw_modal:
        return
    raise base.NoteDraftError(
        "note eyecatch crop dialog has no unique safe save/complete control; "
        + _control_diagnostics(page)
    )


def install() -> None:
    # Reinstall Run189's route/header safety, then replace only Run188's crop completion
    # helper. Run189's captured Run188 upload function resolves this module global at call
    # time, so the new helper is used without weakening header-zone protections.
    run189.install()
    run188._finish_crop_dialog = _finish_crop_dialog


def main() -> None:
    install()
    run185.main()


if __name__ == "__main__":
    main()
