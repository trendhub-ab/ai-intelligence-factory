"""Run181: deterministic visual balance refinement for public note eyecatches.

This layer spends no model requests. It keeps Run180's semantic line breaks, then uses
actual font metrics to make the title up to four pixels larger when the 760px geometry
allows it. The title block moves 30px lower so its visual center sits naturally below
the brand/header row.

Run230 removes the lower subheadline/lead completely. This renderer therefore draws only
the existing brand/tags/background illustration plus the validated title. Run183 reuses
this renderer and raises only the validated conclusion emphasis.
"""
from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as r178


TITLE_FONT_BOOST = 4
TITLE_MAX_FONT = 80
TITLE_MAX_WIDTH = 760
TITLE_Y_SHIFT = 30
# Retained as a compatibility constant for older tests/introspection. Run230 does not draw a subtitle.
SUBTITLE_Y_SHIFT = 16
TITLE_NAVY = (7, 30, 66)
HIGHLIGHT_ORANGE = (242, 140, 40)  # #F28C28
HIGHLIGHT_FONT_SCALE = 1.0
HIGHLIGHT_MAX_FONT = 96
TITLE_SAFE_BOTTOM = 468


def _boost_title_size(lines: list[str], base_size: int) -> int:
    """Return the largest safe size from base..base+4, capped at 80px."""
    try:
        base = int(base_size)
    except (TypeError, ValueError):
        base = 42
    target = min(TITLE_MAX_FONT, base + TITLE_FONT_BOOST)
    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    for candidate in range(target, base - 1, -1):
        font = ee._jp_font(candidate, bold=True)
        if all(ee._text_width(draw, line, font) <= TITLE_MAX_WIDTH for line in lines):
            return candidate
    return base


def _split_line_for_highlight(
    lines: list[str],
    line_index: int,
    highlight_text: str | None,
) -> list[tuple[str, bool]]:
    """Split one title line into normal/highlight runs using global title indices."""
    if not highlight_text:
        return [(lines[line_index], False)]
    joined = "".join(lines)
    start = joined.find(highlight_text)
    if start < 0 or joined.count(highlight_text) != 1:
        return [(lines[line_index], False)]
    end = start + len(highlight_text)
    line_start = sum(len(line) for line in lines[:line_index])
    line_text = lines[line_index]
    line_end = line_start + len(line_text)
    overlap_start = max(start, line_start)
    overlap_end = min(end, line_end)
    if overlap_start >= overlap_end:
        return [(line_text, False)]

    local_start = overlap_start - line_start
    local_end = overlap_end - line_start
    runs: list[tuple[str, bool]] = []
    if local_start:
        runs.append((line_text[:local_start], False))
    runs.append((line_text[local_start:local_end], True))
    if local_end < len(line_text):
        runs.append((line_text[local_end:], False))
    return [(text, emphasized) for text, emphasized in runs if text]


def _run_bbox_height(draw: ImageDraw.ImageDraw, text: str, font: Any) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return max(0, bbox[3] - bbox[1])


def _mixed_line_metrics(
    draw: ImageDraw.ImageDraw,
    runs: list[tuple[str, bool]],
    normal_font: Any,
    highlight_font: Any,
) -> tuple[int, int]:
    width = 0
    height = 0
    for text, emphasized in runs:
        font = highlight_font if emphasized else normal_font
        width += ee._text_width(draw, text, font)
        height = max(height, _run_bbox_height(draw, text, font))
    return width, height


def _fit_highlight_size(
    lines: list[str],
    normal_size: int,
    line_gap: int,
    highlight_text: str | None,
) -> int:
    """Fit one shared emphasis size for all highlighted runs inside the title safe area."""
    if not highlight_text or HIGHLIGHT_FONT_SCALE <= 1.0:
        return int(normal_size)

    base = int(normal_size)
    target = min(HIGHLIGHT_MAX_FONT, max(base, int(round(base * HIGHLIGHT_FONT_SCALE))))
    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    normal_font = ee._jp_font(base, bold=True)
    all_runs = [_split_line_for_highlight(lines, index, highlight_text) for index in range(len(lines))]

    for candidate in range(target, base - 1, -1):
        highlight_font = ee._jp_font(candidate, bold=True)
        heights: list[int] = []
        widths_ok = True
        for runs in all_runs:
            width, height = _mixed_line_metrics(draw, runs, normal_font, highlight_font)
            if width > TITLE_MAX_WIDTH:
                widths_ok = False
                break
            heights.append(height)
        if not widths_ok:
            continue
        block_height = sum(heights) + max(0, len(heights) - 1) * int(line_gap)
        block_bottom = 160 + TITLE_Y_SHIFT + block_height
        if block_bottom <= TITLE_SAFE_BOTTOM or candidate == base:
            return candidate
    return base


def _draw_mixed_title_line(
    draw: ImageDraw.ImageDraw,
    x: int,
    top_y: int,
    runs: list[tuple[str, bool]],
    normal_font: Any,
    highlight_font: Any,
) -> int:
    """Bottom-align visible glyph boxes so mixed-size Japanese remains visually stable."""
    _width, line_height = _mixed_line_metrics(draw, runs, normal_font, highlight_font)
    cursor_x = x
    for text, emphasized in runs:
        font = highlight_font if emphasized else normal_font
        bbox = draw.textbbox((0, 0), text, font=font)
        visible_height = max(0, bbox[3] - bbox[1])
        draw_y = top_y + (line_height - visible_height) - bbox[1]
        color = HIGHLIGHT_ORANGE if emphasized else TITLE_NAVY
        draw.text((cursor_x, draw_y), text, font=font, fill=color)
        cursor_x += ee._text_width(draw, text, font)
    return line_height


def _render_balanced_plan(
    title: str,
    summary: str,
    output_path: str,
    validated: dict[str, Any],
    category: str | None = None,
    date_label: str | None = None,
    *,
    highlight_text: str | None = None,
) -> str:
    """Render Run180 title typography with deterministic Run181/183 balance adjustments."""
    category = (category or ee.infer_editorial_category(title, summary)).strip() or "AI & TECH"
    accent = ee._CATEGORY_ACCENTS.get(category, ee._CATEGORY_ACCENTS["AI & TECH"])
    date_label = date_label or ee.datetime.now(ee.ZoneInfo("Asia/Tokyo")).strftime("%Y.%m")

    import os

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (252, 253, 255))
    draw = ImageDraw.Draw(img)

    ee._draw_network_illustration(draw, accent)
    ee._draw_brand(draw, accent)
    ee._draw_tags(draw, category, date_label, accent)

    title_lines = list(validated["title_lines"])
    title_size = _boost_title_size(title_lines, validated["title_font_size"])
    line_gap = int(validated["title_line_gap"])
    normal_font = ee._jp_font(title_size, bold=True)
    highlight_size = _fit_highlight_size(title_lines, title_size, line_gap, highlight_text)
    highlight_font = ee._jp_font(highlight_size, bold=True)
    y = 160 + TITLE_Y_SHIFT

    for index, _line_text in enumerate(title_lines):
        runs = _split_line_for_highlight(title_lines, index, highlight_text)
        line_height = _draw_mixed_title_line(draw, 48, y, runs, normal_font, highlight_font)
        y += line_height + line_gap

    # Run230: intentionally no lower lead/subheadline and no blue accent rule.
    img.save(output_path, "PNG", optimize=True)
    return output_path


def install(pipeline_module: Any) -> Any:
    """Install the no-API visual balance renderer after Run180."""
    if getattr(pipeline_module, "_RUN181_EYECATCH_VISUAL_BALANCE_INSTALLED", False):
        return pipeline_module

    def balanced_renderer(
        title: str,
        summary: str,
        output_path: str,
        validated: dict[str, Any],
        category: str | None = None,
        date_label: str | None = None,
    ) -> str:
        return _render_balanced_plan(
            title,
            summary,
            output_path,
            validated,
            category=category,
            date_label=date_label,
        )

    r178._render_with_validated_plan = balanced_renderer
    pipeline_module._RUN181_EYECATCH_VISUAL_BALANCE_INSTALLED = True
    pipeline_module.RUN181_EYECATCH_TITLE_FONT_BOOST = TITLE_FONT_BOOST
    pipeline_module.RUN181_EYECATCH_TITLE_Y_SHIFT = TITLE_Y_SHIFT
    pipeline_module.RUN181_EYECATCH_SUBTITLE_Y_SHIFT = SUBTITLE_Y_SHIFT
    pipeline_module.RUN230_EYECATCH_SUBHEADLINE_ENABLED = False
    return pipeline_module
