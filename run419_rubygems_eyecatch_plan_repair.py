#!/usr/bin/env python3
"""Run419: deterministically repair a valid Run180 semantic eyecatch plan.

Run418 correctly refused the raw/base eyecatch fallback, but a real Gemini 3.5 response
could contain a valid semantic eyecatch title while failing only typography partition or
geometry validation. Run419 preserves the semantic title guard and all Production visual
layers, repairs only line breaks/font sizes locally, spends no extra model request, and
then re-validates through Run180 before rendering.
"""
from __future__ import annotations

import argparse
from typing import Any

from PIL import Image, ImageDraw

import run418_rubygems_canonical_eyecatch as r418


def _largest_fitting_size(draw: ImageDraw.ImageDraw, lines: list[str], *, maximum: int, minimum: int, width: int):
    import editorial_eyecatch as ee

    for size in range(maximum, minimum - 1, -1):
        font = ee._jp_font(size, bold=True)
        if all(ee._text_width(draw, line, font) <= width for line in lines):
            return size
    return None


def _repair_layout_plan(source_title: str, subheadline: str, raw_plan: Any) -> dict[str, Any] | None:
    import editorial_eyecatch as ee
    import run178_eyecatch_editorial_layout_optimizer as r178
    import run180_eyecatch_semantic_layout as r180

    if not isinstance(raw_plan, dict):
        return None

    eyecatch_title = r180._validate_eyecatch_title(source_title, raw_plan.get("eyecatch_title"))
    if eyecatch_title is None:
        return None

    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)

    title_lines = r178._coerce_lines(raw_plan.get("title_lines"), 3)
    if (
        title_lines is None
        or r178._canonical_partition_text("".join(title_lines)) != r178._canonical_partition_text(eyecatch_title)
        or not r178._kinsoku_ok(title_lines)
    ):
        _font, title_lines = ee._fit_headline(draw, eyecatch_title, max_width=r180.TITLE_MAX_WIDTH, max_lines=3)
    if (
        not title_lines
        or r178._canonical_partition_text("".join(title_lines)) != r178._canonical_partition_text(eyecatch_title)
        or not r178._kinsoku_ok(title_lines)
    ):
        return None

    title_size = _largest_fitting_size(
        draw,
        title_lines,
        maximum=r180.TITLE_MAX_FONT,
        minimum=r180.TITLE_MIN_FONT,
        width=r180.TITLE_MAX_WIDTH,
    )
    if title_size is None:
        return None

    sub_lines = r178._coerce_lines(raw_plan.get("subheadline_lines"), 2)
    sub_size = None
    if (
        sub_lines is not None
        and r178._canonical_partition_text("".join(sub_lines)) == r178._canonical_partition_text(subheadline)
        and r178._kinsoku_ok(sub_lines)
    ):
        sub_size = _largest_fitting_size(
            draw,
            sub_lines,
            maximum=r180.SUB_MAX_FONT,
            minimum=r180.SUB_MIN_FONT,
            width=r180.SUB_MAX_WIDTH,
        )
    if sub_lines is None or sub_size is None:
        sub_lines = None
        for size in range(r180.SUB_MAX_FONT, r180.SUB_MIN_FONT - 1, -1):
            font = ee._jp_font(size, bold=True)
            candidate = ee._wrap_chars(draw, subheadline, font, r180.SUB_MAX_WIDTH, 2)
            if (
                candidate
                and r178._canonical_partition_text("".join(candidate)) == r178._canonical_partition_text(subheadline)
                and r178._kinsoku_ok(candidate)
                and all(ee._text_width(draw, line, font) <= r180.SUB_MAX_WIDTH for line in candidate)
            ):
                sub_lines = candidate
                sub_size = size
                break
    if not sub_lines or sub_size is None:
        return None

    try:
        line_gap = int(raw_plan.get("title_line_gap"))
    except (TypeError, ValueError):
        line_gap = 12
    line_gap = max(8, min(18, line_gap))

    repaired = {
        "eyecatch_title": eyecatch_title,
        "title_lines": title_lines,
        "title_font_size": title_size,
        "title_line_gap": line_gap,
        "subheadline_lines": sub_lines,
        "subheadline_font_size": sub_size,
        "highlight_text": r180._validate_highlight_text(
            eyecatch_title, title_lines, raw_plan.get("highlight_text")
        ),
    }
    return r180._validate_layout_plan(source_title, subheadline, repaired)


def _render_canonical_repaired():
    pipeline = r418._install_canonical_eyecatch_runtime()
    import editorial_eyecatch as ee
    import run178_eyecatch_editorial_layout_optimizer as r178
    import run180_eyecatch_semantic_layout as r180

    source_title = r180._source_title_for_direction(r418.EXPECTED_NOTE_TITLE)
    existing_headline = ee.editorial_hook_from_title(r418.EXPECTED_NOTE_TITLE, max_chars=48)
    subheadline = ee.editorial_subheadline(r418.SUMMARY, existing_headline)

    original_generate = pipeline._generate_via_chat
    calls: list[str] = []

    def one_layout_call(model: str, *args: Any, **kwargs: Any):
        if calls:
            raise r418.Run418Error("Run419 refuses a second model request")
        if str(model) != r180.EYECATCH_LAYOUT_MODEL or str(model) != "gemini-3.5-flash":
            raise r418.Run418Error(f"Run419 refuses non-3.5 eyecatch model: {model}")
        if str(kwargs.get("request_kind") or "") != "eyecatch_layout":
            raise r418.Run418Error("Run419 model call is not the canonical eyecatch_layout request")
        calls.append(str(model))
        return original_generate(model, *args, **kwargs)

    pipeline._generate_via_chat = one_layout_call
    try:
        raw_plan = r180._request_layout_plan(pipeline, source_title, subheadline)
    finally:
        pipeline._generate_via_chat = original_generate
    if calls != ["gemini-3.5-flash"]:
        raise r418.Run418Error(f"Run419 expected exactly one Gemini 3.5 call, got {calls!r}")

    validated = r180._validate_layout_plan(source_title, subheadline, raw_plan)
    repaired = False
    if validated is None:
        validated = _repair_layout_plan(source_title, subheadline, raw_plan)
        repaired = validated is not None
    if validated is None:
        raise r418.Run418Error("Run419 semantic title invalid or deterministic geometry repair failed")

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
        raise r418.Run418Error("Run419 canonical eyecatch render missing or unexpectedly small")
    with Image.open(r418.OUTPUT) as image:
        if image.size != (1280, 670) or image.format != "PNG":
            raise r418.Run418Error(f"Run419 canonical eyecatch geometry invalid: {image.size} {image.format}")

    return r418.OUTPUT, {
        "layout_title": str(validated.get("eyecatch_title") or ""),
        "title_lines": list(validated.get("title_lines") or []),
        "highlight_text": str(validated.get("highlight_text") or ""),
        "plan_repaired_deterministically": repaired,
        "gemini_3_5_calls": 1,
        "gemini_3_8_calls": 0,
    }


def render_and_attach() -> dict[str, Any]:
    r418._fetch_exact_target(require_broken=True)
    path, plan = _render_canonical_repaired()
    upload_id = r418._upload_replace(path)
    return {
        "status": "canonical_eyecatch_attached",
        "page_id": r418.PAGE_ID,
        "file": r418.FIXED_FILENAME,
        "bytes": path.stat().st_size,
        "upload_id": upload_id,
        "body_changed": False,
        "public_release": False,
        **plan,
    }


def refresh_existing_private_draft() -> dict[str, Any]:
    return r418.refresh_existing_private_draft()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("render-attach", "refresh-draft"))
    args = parser.parse_args()
    if r418.os.getenv("RUN418_CONFIRM", "").strip() != r418.CONFIRM:
        raise r418.Run418Error("Run419 exact-target confirmation missing")
    result = render_and_attach() if args.mode == "render-attach" else refresh_existing_private_draft()
    print(r418.json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
