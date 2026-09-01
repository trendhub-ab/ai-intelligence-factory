"""Run181: deterministic visual balance refinement for public note eyecatches.

This layer spends no model requests.  It keeps Run180's semantic line breaks, then uses
actual font metrics to make the title up to four pixels larger when the 760px geometry
allows it.  The title block moves 30px lower and the subheadline 16px lower so the card's
visual center sits more naturally below the brand/header row.
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
SUBTITLE_Y_SHIFT = 16
TITLE_NAVY = (7, 30, 66)
HIGHLIGHT_ORANGE = (242, 140, 40)  # #F28C28


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
    """Render Run180 typography with deterministic Run181 balance adjustments."""
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
    headline_font = ee._jp_font(title_size, bold=True)
    y = 160 + TITLE_Y_SHIFT

    for index, line_text in enumerate(title_lines):
        bbox = draw.textbbox((0, 0), line_text, font=headline_font)
        draw_y = y - bbox[1]
        cursor_x = 48
        for segment, emphasized in _split_line_for_highlight(title_lines, index, highlight_text):
            color = HIGHLIGHT_ORANGE if emphasized else TITLE_NAVY
            draw.text((cursor_x, draw_y), segment, font=headline_font, fill=color)
            cursor_x += ee._text_width(draw, segment, headline_font)
        y += (bbox[3] - bbox[1]) + int(validated["title_line_gap"])

    base_sub_y = min(535, max(485, y + 18))
    sub_y = min(551, base_sub_y + SUBTITLE_Y_SHIFT)
    draw.rectangle((48, sub_y + 2, 53, sub_y + 42), fill=accent)
    sub_font = ee._jp_font(int(validated["subheadline_font_size"]), bold=True)
    sub_step = max(34, int(validated["subheadline_font_size"]) + 11)
    for index, line_text in enumerate(validated["subheadline_lines"]):
        draw.text((72, sub_y + index * sub_step), line_text, font=sub_font, fill=(18, 42, 79))

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
    return pipeline_module
