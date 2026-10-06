"""Run222: keep public-note footer order and editor presentation human-clean.

Production intent:
- keep Sources / Evidence and the article disclaimer attached to the article itself;
- place the subscriber CTA after those trust/provenance blocks so the CTA is the final action;
- remove a duplicated leading H1 when note already has the same title in its title field;
- never expose a raw Markdown ``# `` heading in note body presentation;
- remove supported fenced-code language labels at the explicit note-presentation boundary because
  note readback does not preserve that metadata, while preserving code text byte-for-byte;
- preserve the stored current-publication-contract manuscript for validation before applying
  note-editor-only presentation transforms;
- zero Gemini/model calls and no public-release action.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

CTA_HEADINGS = {
    "「自分はどうする？」まで判断したい方へ",
    "調査と判断の時間を減らしたい方へ",
    "有料サブスクのご案内",
}
SOURCE_HEADING = "Sources / Evidence"
_FENCE_LANGUAGE = re.compile(r"^(\s*)```([A-Za-z0-9][A-Za-z0-9_+.#-]{0,39})\s*$")


def find_header_image_add_button(note_module: Any, page: Any) -> Any | None:
    """Find the current note header-image control; ambiguous geometry always fails closed."""
    semantic = note_module._topmost_visible(page.locator(note_module._header_image_add_selector()))
    if semantic is not None:
        return semantic
    try:
        page.evaluate(
            """() => {
                window.scrollTo(0, 0);
                for (const el of document.querySelectorAll('*')) {
                    if (el.scrollTop > 0) el.scrollTop = 0;
                }
            }"""
        )
        page.wait_for_timeout(1500)
        index = page.evaluate(
            """() => {
                const bs = [...document.querySelectorAll('button')];
                const matches = bs.map((b, i) => {
                    const r = b.getBoundingClientRect();
                    const label = (b.getAttribute('aria-label') || b.innerText || '').trim();
                    const ok = !label && r.width >= 30 && r.width <= 56 &&
                        r.y > 60 && r.y < 220 && r.x > 400;
                    return ok ? i : -1;
                }).filter((i) => i >= 0);
                return matches.length === 1 ? matches[0] : -1;
            }"""
        )
    except Exception:
        return None
    if not isinstance(index, int) or index < 0:
        return None
    try:
        candidate = page.locator("button").nth(index)
        if candidate.is_visible(timeout=700):
            return candidate
    except Exception:
        pass
    return None


def _upload_header_image_current(note_module: Any, page: Any, image_path: Path) -> None:
    add_button = find_header_image_add_button(note_module, page)
    if add_button is None:
        raise note_module.NoteDraftError("note header-image control was not found")
    add_button.click()

    upload_button = note_module._first_visible(
        page,
        ['button:has-text("画像をアップロード")', '[role="button"]:has-text("画像をアップロード")'],
        timeout_ms=5000,
    )
    chooser_used = False
    if upload_button is not None:
        try:
            with page.expect_file_chooser(timeout=5000) as chooser_info:
                upload_button.click()
            chooser_info.value.set_files(str(image_path))
            chooser_used = True
        except Exception:
            chooser_used = False
    if not chooser_used:
        file_input = page.locator('input[type="file"]').first
        try:
            file_input.wait_for(state="attached", timeout=7000)
            file_input.set_input_files(str(image_path))
        except Exception as exc:
            raise note_module.NoteDraftError("note eyecatch file chooser was not available") from exc

    page.wait_for_timeout(1200)
    dialog = page.locator('[role="dialog"]').first
    try:
        dialog_visible = dialog.is_visible(timeout=2500)
    except Exception:
        dialog_visible = False
    if dialog_visible:
        save_button = dialog.get_by_role("button", name=re.compile(r"^保存$")).first
        try:
            save_button.wait_for(state="visible", timeout=10000)
            deadline = time.time() + 20
            while time.time() < deadline and not save_button.is_enabled():
                page.wait_for_timeout(300)
            if not save_button.is_enabled():
                raise note_module.NoteDraftError("note eyecatch crop dialog never became saveable")
            save_button.click()
            dialog.wait_for(state="hidden", timeout=15000)
        except note_module.NoteDraftError:
            raise
        except Exception as exc:
            raise note_module.NoteDraftError("note eyecatch crop/save step failed") from exc

    page.wait_for_timeout(1000)
    error_locator = page.locator('text=/アップロード.*(失敗|できません|エラー)/').first
    try:
        if error_locator.is_visible(timeout=800):
            raise note_module.NoteDraftError("note reported an eyecatch upload error")
    except note_module.NoteDraftError:
        raise
    except Exception:
        pass


def _install_header_control(note_module: Any) -> None:
    def installed_find(page: Any) -> Any | None:
        return find_header_image_add_button(note_module, page)

    def installed_upload(page: Any, image_path: Path) -> None:
        _upload_header_image_current(note_module, page, image_path)

    note_module._find_header_image_add_button = installed_find
    note_module._upload_header_image = installed_upload


def _plain_heading(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _find_h3(text: str, labels: set[str]) -> re.Match[str] | None:
    for match in re.finditer(r"(?m)^\s*###\s+(.+?)\s*$", text):
        if _plain_heading(match.group(1)) in labels:
            return match
    return None


def _preceding_divider(text: str, before: int, *, lower_bound: int = 0) -> int | None:
    matches = list(re.finditer(r"(?m)^\s*---\s*$", text[lower_bound:before]))
    if not matches:
        return None
    return lower_bound + matches[-1].start()


def move_subscription_cta_after_evidence(markdown_text: str) -> str:
    """Move the subscriber CTA after Sources/Evidence + disclaimer, idempotently.

    The function can normalize a manuscript that still has the pre-Run222 footer order, but the
    note browser path calls it only *after* the manuscript has satisfied the current Publication
    Contract. A manuscript stamped under an older policy must first be deterministically rebuilt
    and restamped under the current policy; stale provenance is never accepted or bypassed.
    """
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    cta = _find_h3(text, CTA_HEADINGS)
    source = _find_h3(text, {SOURCE_HEADING})
    if cta is None or source is None or cta.start() > source.start():
        return text
    cta_start = _preceding_divider(text, cta.start())
    if cta_start is None:
        cta_start = cta.start()
    source_start = _preceding_divider(text, source.start(), lower_bound=cta.end())
    if source_start is None or source_start <= cta_start:
        source_start = source.start()
    cta_block = text[cta_start:source_start].strip()
    prefix = text[:cta_start].rstrip()
    evidence_and_disclaimer = text[source_start:].strip()
    if not cta_block or not evidence_and_disclaimer:
        return text
    parts = [part for part in (prefix, evidence_and_disclaimer, cta_block) if part]
    return "\n\n".join(parts).strip()


def _normalize_title(value: str) -> str:
    text = _plain_heading(value)
    text = text.replace("　", " ")
    return re.sub(r"\s+", " ", text).strip()


def _strip_duplicate_leading_h1(markdown_text: str, title: str) -> str:
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n")
    match = re.match(r"^\s*#\s+(.+?)\s*(?:\n+|$)", text)
    if match and _normalize_title(match.group(1)) == _normalize_title(title):
        text = text[match.end():]
    return text.lstrip("\n")


def strip_fenced_code_language_metadata(markdown_text: str) -> str:
    """Remove only simple fenced-code language labels before canonical note delivery."""
    out: list[str] = []
    in_code = False
    for line in str(markdown_text or "").split("\n"):
        stripped = line.strip()
        if not in_code:
            match = _FENCE_LANGUAGE.fullmatch(line)
            if match:
                out.append(f"{match.group(1)}```")
                in_code = True
                continue
            if stripped == "```":
                in_code = True
        elif stripped == "```":
            in_code = False
        out.append(line)
    return "\n".join(out)


def _demote_body_h1_outside_code(markdown_text: str) -> str:
    """note title field is the document H1; body-level H1 becomes H2, code fences untouched."""
    out: list[str] = []
    in_code = False
    for line in str(markdown_text or "").split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if not in_code and re.match(r"^\s*#\s+\S", line):
            line = re.sub(r"^(\s*)#\s+", r"\1## ", line, count=1)
        out.append(line)
    return "\n".join(out)


def prepare_note_editor_manuscript(markdown_text: str, title: str) -> str:
    """Presentation-only transform applied after stored manuscript validation."""
    text = move_subscription_cta_after_evidence(markdown_text)
    text = _strip_duplicate_leading_h1(text, title)
    text = strip_fenced_code_language_metadata(text)
    text = _demote_body_h1_outside_code(text)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def install_pipeline(pipeline_module: Any) -> Any:
    """Ensure newly generated canonical manuscripts end with the CTA after provenance."""
    if getattr(pipeline_module, "_run222_pipeline_installed", False):
        return pipeline_module
    original = pipeline_module.build_clean_note_manuscript

    def build_clean_note_manuscript(*args: Any, **kwargs: Any) -> str:
        return move_subscription_cta_after_evidence(original(*args, **kwargs))

    pipeline_module.build_clean_note_manuscript = build_clean_note_manuscript
    pipeline_module._run222_pipeline_installed = True
    return pipeline_module


def install_note(note_module: Any) -> Any:
    """Transform only after whichever current-contract guard already wraps _prepare_article."""
    _install_header_control(note_module)
    if getattr(note_module, "_run222_note_installed", False):
        return note_module
    original = note_module._prepare_article

    def _prepare_article(requested_sync_id: str = "") -> dict[str, Any]:
        article = original(requested_sync_id)
        article = dict(article)
        article["manuscript"] = prepare_note_editor_manuscript(
            str(article.get("manuscript") or ""), str(article.get("title") or "")
        )
        return article

    note_module._prepare_article = _prepare_article
    note_module._run222_note_installed = True
    return note_module
