from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import note_draft_automation as note_base


TOKENS = ("画像", "見出し", "ヘッダー", "アイキャッチ", "cover", "header", "image", "photo", "upload")


def _clean(value: object, limit: int = 100) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _attr(locator, name: str) -> str:
    try:
        return _clean(locator.get_attribute(name))
    except Exception:
        return ""


def _visible(locator) -> bool:
    try:
        return bool(locator.is_visible(timeout=120))
    except Exception:
        return False


def _box(locator) -> dict[str, float] | None:
    try:
        raw = locator.bounding_box()
    except Exception:
        raw = None
    if not raw:
        return None
    return {key: round(float(raw.get(key, 0.0)), 1) for key in ("x", "y", "width", "height")}


def _route_kind(url: str) -> dict[str, str]:
    parsed = urlparse(str(url or ""))
    path = parsed.path or ""
    if path.rstrip("/") in {"/new", "/notes/new"}:
        kind = "new"
    elif re.search(r"/notes/[^/]+/edit/?$", path):
        kind = "edit"
    elif any(token in path.lower() for token in ("login", "signin", "signup")):
        kind = "auth"
    else:
        kind = "other"
    return {"host": parsed.hostname or "", "path_kind": kind}


def collect() -> dict[str, object]:
    storage_path = note_base._decode_storage_state()
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--lang=ja-JP"])
            context = browser.new_context(
                storage_state=str(storage_path),
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                viewport={"width": 1440, "height": 1100},
            )
            page = context.new_page()
            page.set_default_timeout(15000)
            try:
                page.goto(note_base.NOTE_NEW_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                if note_base._looks_logged_out(page):
                    raise RuntimeError("note_auth_inactive")

                title = note_base._find_title(page)
                title_box = _box(title)
                title_y = float((title_box or {}).get("y", 999999.0))

                file_inputs: list[dict[str, object]] = []
                inputs = page.locator('input[type="file"]')
                for index in range(min(inputs.count(), 20)):
                    item = inputs.nth(index)
                    file_inputs.append({
                        "index": index,
                        "visible": _visible(item),
                        "box": _box(item),
                        "accept": _attr(item, "accept"),
                        "multiple": _attr(item, "multiple"),
                        "aria_label": _attr(item, "aria-label"),
                        "title": _attr(item, "title"),
                        "data_testid": _attr(item, "data-testid"),
                        "name": _attr(item, "name"),
                        "class": _attr(item, "class"),
                    })

                controls: list[dict[str, object]] = []
                locator = page.locator('button, [role="button"]')
                for index in range(min(locator.count(), 180)):
                    item = locator.nth(index)
                    if not _visible(item):
                        continue
                    box = _box(item)
                    if not box:
                        continue
                    try:
                        text = _clean(item.inner_text(timeout=150), 80)
                    except Exception:
                        text = ""
                    aria_label = _attr(item, "aria-label")
                    title_attr = _attr(item, "title")
                    data_testid = _attr(item, "data-testid")
                    name = _attr(item, "name")
                    semantic = " ".join((text, aria_label, title_attr, data_testid, name)).lower()
                    token_match = any(token.lower() in semantic for token in TOKENS)
                    near_title = float(box["y"]) < title_y + 140 and float(box["y"]) > max(-100.0, title_y - 260)
                    try:
                        svg_count = int(item.locator("svg").count())
                        img_count = int(item.locator("img").count())
                    except Exception:
                        svg_count = img_count = 0
                    if not (token_match or near_title):
                        continue
                    controls.append({
                        "index": index,
                        "box": box,
                        "near_title": near_title,
                        "token_match": token_match,
                        "text": text,
                        "aria_label": aria_label,
                        "title": title_attr,
                        "data_testid": data_testid,
                        "name": name,
                        "class": _attr(item, "class"),
                        "svg_count": svg_count,
                        "img_count": img_count,
                    })

                controls.sort(key=lambda row: (float((row.get("box") or {}).get("y", 999999)), float((row.get("box") or {}).get("x", 999999))))
                return {
                    "status": "diagnostic_complete",
                    "read_only": True,
                    "note_mutation_count": 0,
                    "zero_model_calls": True,
                    "public_release": False,
                    "route": _route_kind(str(page.url or "")),
                    "title_geometry": title_box,
                    "file_input_count": len(file_inputs),
                    "file_inputs": file_inputs,
                    "candidate_control_count": len(controls),
                    "candidate_controls": controls[:60],
                }
            finally:
                context.close()
                browser.close()
    finally:
        storage_path.unlink(missing_ok=True)


def main() -> int:
    result = collect()
    path_value = str(os.environ.get("P0B_HEADER_PROBE_RESULT") or "").strip()
    if path_value:
        target = Path(path_value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
