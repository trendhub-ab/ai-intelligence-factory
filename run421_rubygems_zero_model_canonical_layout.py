#!/usr/bin/env python3
"""Run421: exact RubyGems eyecatch repair with zero model requests.

Two authenticated Run180 Gemini 3.5 calls returned HTTP 200 but invalid semantic plans.
For this exact already-approved article, stop spending model quota. Reuse the existing
source-bounded editorial hook as copy, deterministically rebuild typography, and render
through the already-installed Production visual stack (Run179/181/182/183/296).
"""
from __future__ import annotations

import argparse
from typing import Any

from PIL import Image

import run418_rubygems_canonical_eyecatch as r418
import run419_rubygems_eyecatch_plan_repair as r419


def _deterministic_plan() -> dict[str, Any]:
    r418._install_canonical_eyecatch_runtime()
    import editorial_eyecatch as ee
    import run180_eyecatch_semantic_layout as r180

    source_title = r180._source_title_for_direction(r418.EXPECTED_NOTE_TITLE)
    eyecatch_title = ee.editorial_hook_from_title(r418.EXPECTED_NOTE_TITLE, max_chars=48)
    existing_headline = eyecatch_title
    subheadline = ee.editorial_subheadline(r418.SUMMARY, existing_headline)
    highlight = "RubyGems騒動" if "RubyGems騒動" in eyecatch_title else ""
    raw = {
        "eyecatch_title": eyecatch_title,
        "title_lines": [],
        "title_font_size": r180.TITLE_MAX_FONT,
        "title_line_gap": 12,
        "subheadline_lines": [],
        "subheadline_font_size": r180.SUB_MAX_FONT,
        "highlight_text": highlight,
    }
    validated = r419._repair_layout_plan(source_title, subheadline, raw)
    if validated is None:
        raise r418.Run418Error("Run421 deterministic source-bounded copy failed Run180 validation")
    return validated


def _render_zero_model():
    # Install first so Run181/182/183/296 own the live validated-plan renderer.
    r418._install_canonical_eyecatch_runtime()
    import run178_eyecatch_editorial_layout_optimizer as r178

    validated = _deterministic_plan()
    r418.OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = r178._render_with_validated_plan(
        r418.EXPECTED_NOTE_TITLE,
        r418.SUMMARY,
        str(r418.OUTPUT),
        validated,
        category=r418.CATEGORY,
        date_label=None,
    )
    if str(result) != str(r418.OUTPUT) or not r418.OUTPUT.exists() or r418.OUTPUT.stat().st_size < 10_000:
        raise r418.Run418Error("Run421 canonical eyecatch render missing or unexpectedly small")
    with Image.open(r418.OUTPUT) as image:
        if image.size != (1280, 670) or image.format != "PNG":
            raise r418.Run418Error(f"Run421 canonical eyecatch geometry invalid: {image.size} {image.format}")
    return r418.OUTPUT, validated


def render_and_attach() -> dict[str, Any]:
    r418._fetch_exact_target(require_broken=True)
    path, plan = _render_zero_model()
    upload_id = r418._upload_replace(path)
    return {
        "status": "canonical_eyecatch_attached",
        "page_id": r418.PAGE_ID,
        "file": r418.FIXED_FILENAME,
        "bytes": path.stat().st_size,
        "upload_id": upload_id,
        "layout_title": str(plan.get("eyecatch_title") or ""),
        "title_lines": list(plan.get("title_lines") or []),
        "highlight_text": str(plan.get("highlight_text") or ""),
        "gemini_calls": 0,
        "body_changed": False,
        "public_release": False,
    }


def refresh_existing_private_draft() -> dict[str, Any]:
    return r418.refresh_existing_private_draft()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("render-attach", "refresh-draft"))
    args = parser.parse_args()
    if r418.os.getenv("RUN418_CONFIRM", "").strip() != r418.CONFIRM:
        raise r418.Run418Error("Run421 exact-target confirmation missing")
    result = render_and_attach() if args.mode == "render-attach" else refresh_existing_private_draft()
    print(r418.json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
