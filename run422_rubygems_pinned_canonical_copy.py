#!/usr/bin/env python3
"""Run422/423: exact RubyGems canonical eyecatch with safe semantic line breaks.

Run422 restored the canonical 2–3-line copy contract. Run423 tightens that contract after
the real render split the protected Latin identifier ``RubyGems`` across lines. For this
exact already-approved article, keep the pinned source-bounded copy and pre-seed semantic
line boundaries that preserve protected identifiers. No model request is used. All pixels
are rendered by the installed Production visual stack inherited from Run418/419/421.
"""
from __future__ import annotations

import argparse
import re
from typing import Any

from PIL import Image

import run418_rubygems_canonical_eyecatch as r418
import run419_rubygems_eyecatch_plan_repair as r419

PINNED_EYECATCH_TITLE = "OpenAIエージェントとRubyGems、権限管理の境界線"
PINNED_TITLE_LINES = ("OpenAIエージェントと", "RubyGems、権限管理の境界線")
PINNED_SUBHEADLINE = "AIエージェントの権限設計を考える"
PINNED_HIGHLIGHT = "権限管理の境界線"


def _latin_tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[A-Za-z][A-Za-z0-9._+-]*", text or ""))


def _require_bounded_title_lines(validated: dict[str, Any]) -> dict[str, Any]:
    """Keep the latest canonical contract: fixed area, 2–3 lines, no Latin-token split."""
    title_lines = [str(line).strip() for line in (validated.get("title_lines") or []) if str(line).strip()]
    if len(title_lines) not in (2, 3):
        raise r418.Run418Error(
            f"Run423 canonical headline must occupy 2 or 3 lines, got {len(title_lines)}"
        )
    if "".join(title_lines) != PINNED_EYECATCH_TITLE:
        raise r418.Run418Error("Run423 title-line partition changed canonical copy")
    for token in _latin_tokens(PINNED_EYECATCH_TITLE):
        containing = [line for line in title_lines if token in line]
        if len(containing) != 1:
            raise r418.Run418Error(f"Run423 refuses split Latin identifier: {token}")
    validated = dict(validated)
    validated["title_lines"] = title_lines
    return validated


def _pinned_plan() -> dict[str, Any]:
    r418._install_canonical_eyecatch_runtime()
    import run180_eyecatch_semantic_layout as r180

    source_title = r180._source_title_for_direction(r418.EXPECTED_NOTE_TITLE)
    if r180._validate_eyecatch_title(source_title, PINNED_EYECATCH_TITLE) != PINNED_EYECATCH_TITLE:
        raise r418.Run418Error("Run423 pinned eyecatch title failed Run180 semantic guard")

    raw = {
        "eyecatch_title": PINNED_EYECATCH_TITLE,
        "title_lines": list(PINNED_TITLE_LINES),
        "title_font_size": r180.TITLE_MAX_FONT,
        "title_line_gap": 12,
        "subheadline_lines": [],
        "subheadline_font_size": r180.SUB_MAX_FONT,
        "highlight_text": PINNED_HIGHLIGHT,
    }
    validated = r419._repair_layout_plan(source_title, PINNED_SUBHEADLINE, raw)
    if validated is None:
        raise r418.Run418Error("Run423 pinned source-bounded copy failed Run180 geometry validation")
    if validated.get("eyecatch_title") != PINNED_EYECATCH_TITLE:
        raise r418.Run418Error("Run423 semantic title changed during deterministic layout")
    return _require_bounded_title_lines(validated)


def _render_zero_model():
    r418._install_canonical_eyecatch_runtime()
    import run178_eyecatch_editorial_layout_optimizer as r178

    validated = _pinned_plan()
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
        raise r418.Run418Error("Run423 canonical eyecatch render missing or unexpectedly small")
    with Image.open(r418.OUTPUT) as image:
        if image.size != (1280, 670) or image.format != "PNG":
            raise r418.Run418Error(f"Run423 canonical eyecatch geometry invalid: {image.size} {image.format}")
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
        "subheadline_lines": list(plan.get("subheadline_lines") or []),
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
        raise r418.Run418Error("Run423 exact-target confirmation missing")
    result = render_and_attach() if args.mode == "render-attach" else refresh_existing_private_draft()
    print(r418.json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
