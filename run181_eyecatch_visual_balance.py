"""Run181: deterministic visual balance and impact hierarchy for public note eyecatches.

This layer spends no model requests. It keeps Run180's semantic line breaks and Run182/183
orange emphasis, while rendering the adopted copy-led hierarchy on the already-approved
white/network illustration:

* compact reader-purpose badge;
* short editorial hook above the title;
* larger/lower main title with restrained orange emphasis;
* source-bounded subheadline below the title;
* compact category/date footer.

The background, right-side network illustration, brand and top tags remain the existing
``editorial_eyecatch`` deterministic functions.  No image-generation API or additional
Gemini request is introduced.
"""
from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as r178


# Historical Run181 compatibility constants.  Keep these stable for downstream contracts.
TITLE_FONT_BOOST = 4
TITLE_MAX_FONT = 80
TITLE_MAX_WIDTH = 760
TITLE_Y_SHIFT = 30
SUBTITLE_Y_SHIFT = 16
TITLE_NAVY = (7, 30, 66)
HIGHLIGHT_ORANGE = (242, 140, 40)  # #F28C28
HIGHLIGHT_FONT_SCALE = 1.0
HIGHLIGHT_MAX_FONT = 96
TITLE_SAFE_BOTTOM = 468

# Adopted impact hierarchy.  These are deterministic presentation values only.
IMPACT_BADGE_TOP = 112
IMPACT_HOOK_TOP = 174
IMPACT_TITLE_TOP = 234
IMPACT_TITLE_SAFE_BOTTOM = 500
IMPACT_TITLE_FONT_BOOST = 8
IMPACT_TITLE_MAX_FONT = 88
IMPACT_HIGHLIGHT_MAX_FONT = 104
IMPACT_SUBTITLE_MIN_TOP = 510
IMPACT_FOOTER_TOP = 625
IMPACT_LEFT = 48
IMPACT_TEXT_RIGHT = 808


def _boost_title_size(lines: list[str], base_size: int) -> int:
    """Historical Run181 fitter retained for compatibility tests and callers."""
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
    """Historical Run183 fitter retained as a stable helper."""
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


def _pale(color: tuple[int, int, int], factor: float = 0.88) -> tuple[int, int, int]:
    return tuple(int(round(channel + (255 - channel) * factor)) for channel in color)


def _editorial_badge(title: str, summary: str, category: str) -> str:
    """Choose one short reader-purpose label without inventing article facts."""
    text = f"{title}\n{summary}".lower()
    if any(token in text for token in (" vs ", "vs.", "比較", "違い", "どちら")):
        return "比較で理解"
    if category == "SECURITY" or any(token in text for token in ("脆弱", "攻撃", "security", "安全性")):
        return "安全性を確認"
    if category == "RESEARCH":
        return "論文をやさしく"
    if any(token in text for token in ("導入", "採用", "使うべき", "実務", "運用")):
        return "実務で判断"
    return "初心者向け"


def _editorial_hook(title: str, summary: str, category: str) -> str:
    """Return a compact curiosity hook that adds no factual claim."""
    text = f"{title}\n{summary}".lower()
    if any(token in text for token in (" vs ", "vs.", "比較", "違い", "どちら")):
        return "結局、どこが違うのか？"
    if category == "SECURITY" or any(token in text for token in ("脆弱", "攻撃", "security", "安全性")):
        return "まず、何が危ないのか？"
    if any(token in text for token in ("速い", "高速", "強い", "高性能", "性能")):
        return "結局、何がすごいのか？"
    if category == "RESEARCH":
        return "この話、どこが重要？"
    if "？" in title or "?" in title:
        return "答えを、わかりやすく。"
    return "結局、何が重要なのか？"


def _impact_title_size(lines: list[str], base_size: int, line_gap: int) -> int:
    """Make the main copy as large as geometry allows, including vertical fit."""
    try:
        base = max(48, int(base_size))
    except (TypeError, ValueError):
        base = 60
    target = min(IMPACT_TITLE_MAX_FONT, base + IMPACT_TITLE_FONT_BOOST)
    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    for candidate in range(target, 47, -1):
        font = ee._jp_font(candidate, bold=True)
        widths = [ee._text_width(draw, line, font) for line in lines]
        heights = [_run_bbox_height(draw, line, font) for line in lines]
        block_height = sum(heights) + max(0, len(lines) - 1) * int(line_gap)
        if (
            all(width <= TITLE_MAX_WIDTH for width in widths)
            and IMPACT_TITLE_TOP + block_height <= IMPACT_TITLE_SAFE_BOTTOM
        ):
            return candidate
    return min(base, IMPACT_TITLE_MAX_FONT)


def _fit_impact_highlight_size(
    lines: list[str], normal_size: int, line_gap: int, highlight_text: str | None
) -> int:
    if not highlight_text or HIGHLIGHT_FONT_SCALE <= 1.0:
        return int(normal_size)
    base = int(normal_size)
    target = min(
        IMPACT_HIGHLIGHT_MAX_FONT,
        max(base, int(round(base * HIGHLIGHT_FONT_SCALE))),
    )
    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    normal_font = ee._jp_font(base, bold=True)
    all_runs = [_split_line_for_highlight(lines, index, highlight_text) for index in range(len(lines))]

    for candidate in range(target, base - 1, -1):
        highlight_font = ee._jp_font(candidate, bold=True)
        heights: list[int] = []
        fits = True
        for runs in all_runs:
            width, height = _mixed_line_metrics(draw, runs, normal_font, highlight_font)
            if width > TITLE_MAX_WIDTH:
                fits = False
                break
            heights.append(height)
        if not fits:
            continue
        block_height = sum(heights) + max(0, len(heights) - 1) * int(line_gap)
        if IMPACT_TITLE_TOP + block_height <= IMPACT_TITLE_SAFE_BOTTOM:
            return candidate
    return base


def _draw_badge(
    draw: ImageDraw.ImageDraw,
    label: str,
    accent: tuple[int, int, int],
) -> None:
    font = ee._jp_font(22, bold=True)
    text_w = ee._text_width(draw, label, font)
    x0, y0 = IMPACT_LEFT, IMPACT_BADGE_TOP
    x1, y1 = x0 + text_w + 56, y0 + 42
    draw.rounded_rectangle((x0, y0, x1, y1), radius=21, fill=_pale(accent, 0.89))
    draw.rounded_rectangle((x0 + 14, y0 + 14, x0 + 26, y0 + 28), radius=3, fill=accent)
    draw.text((x0 + 36, y0 + 8), label, font=font, fill=TITLE_NAVY)


def _draw_hook(
    draw: ImageDraw.ImageDraw,
    hook: str,
    accent: tuple[int, int, int],
) -> None:
    font = ee._jp_font(31, bold=True)
    bbox = draw.textbbox((0, 0), hook, font=font)
    text_w = max(0, bbox[2] - bbox[0])
    draw.text((IMPACT_LEFT, IMPACT_HOOK_TOP - bbox[1]), hook, font=font, fill=TITLE_NAVY)
    underline_right = min(IMPACT_TEXT_RIGHT, IMPACT_LEFT + text_w + 18)
    draw.rounded_rectangle(
        (IMPACT_LEFT, IMPACT_HOOK_TOP + 38, underline_right, IMPACT_HOOK_TOP + 44),
        radius=3,
        fill=_pale(accent, 0.83),
    )


def _subheadline_lines(
    draw: ImageDraw.ImageDraw,
    title: str,
    summary: str,
    validated: dict[str, Any],
) -> tuple[list[str], int]:
    existing = validated.get("subheadline_lines")
    if isinstance(existing, list) and existing and all(isinstance(line, str) and line.strip() for line in existing):
        lines = [line.strip() for line in existing[:2]]
        try:
            size = int(validated.get("subheadline_font_size", 26))
        except (TypeError, ValueError):
            size = 26
        return lines, max(22, min(29, size))

    eyecatch_title = str(validated.get("eyecatch_title") or title or "")
    text = ee.editorial_subheadline(summary, eyecatch_title)
    size = 26
    font = ee._jp_font(size, bold=True)
    return ee._wrap_chars(draw, text, font, 725, 2), size


def _draw_footer(
    draw: ImageDraw.ImageDraw,
    category: str,
    date_label: str,
) -> None:
    label_font = ee._latin_font(18, bold=True)
    date_font = ee._latin_font(18, bold=True)
    label = f"{category} / 解説"
    draw.text((IMPACT_LEFT, IMPACT_FOOTER_TOP), label, font=label_font, fill=(18, 42, 79))
    label_w = ee._text_width(draw, label, label_font)
    divider_x = IMPACT_LEFT + label_w + 18
    draw.line((divider_x, IMPACT_FOOTER_TOP - 1, divider_x, IMPACT_FOOTER_TOP + 24), fill=(185, 201, 222), width=2)
    draw.text((divider_x + 18, IMPACT_FOOTER_TOP), date_label, font=date_font, fill=(18, 42, 79))


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
    """Render the adopted copy-led hierarchy over the unchanged deterministic background."""
    category = (category or ee.infer_editorial_category(title, summary)).strip() or "AI & TECH"
    accent = ee._CATEGORY_ACCENTS.get(category, ee._CATEGORY_ACCENTS["AI & TECH"])
    date_label = date_label or ee.datetime.now(ee.ZoneInfo("Asia/Tokyo")).strftime("%Y.%m")

    import os

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (252, 253, 255))
    draw = ImageDraw.Draw(img)

    # Approved background/right illustration contract: these calls are intentionally unchanged.
    ee._draw_network_illustration(draw, accent)
    ee._draw_brand(draw, accent)
    ee._draw_tags(draw, category, date_label, accent)

    _draw_badge(draw, _editorial_badge(title, summary, category), accent)
    _draw_hook(draw, _editorial_hook(title, summary, category), accent)

    title_lines = [str(line) for line in validated.get("title_lines", []) if str(line).strip()]
    if not title_lines:
        fallback = ee.editorial_hook_from_title(title, max_chars=48)
        _font, title_lines = ee._fit_headline(draw, fallback, max_width=TITLE_MAX_WIDTH, max_lines=3)
    line_gap = max(8, min(18, int(validated.get("title_line_gap", 12))))
    title_size = _impact_title_size(title_lines, int(validated.get("title_font_size", 60)), line_gap)
    normal_font = ee._jp_font(title_size, bold=True)
    highlight_size = _fit_impact_highlight_size(title_lines, title_size, line_gap, highlight_text)
    highlight_font = ee._jp_font(highlight_size, bold=True)

    y = IMPACT_TITLE_TOP
    for index, _line_text in enumerate(title_lines):
        runs = _split_line_for_highlight(title_lines, index, highlight_text)
        line_height = _draw_mixed_title_line(draw, IMPACT_LEFT, y, runs, normal_font, highlight_font)
        y += line_height + line_gap
    title_bottom = y - line_gap

    sub_lines, sub_size = _subheadline_lines(draw, title, summary, validated)
    sub_top = max(IMPACT_SUBTITLE_MIN_TOP, title_bottom + 18)
    sub_font = ee._jp_font(sub_size, bold=True)
    sub_step = max(34, sub_size + 10)
    for index, line_text in enumerate(sub_lines[:2]):
        bbox = draw.textbbox((0, 0), line_text, font=sub_font)
        draw.text(
            (IMPACT_LEFT, sub_top + index * sub_step - bbox[1]),
            line_text,
            font=sub_font,
            fill=(18, 42, 79),
        )

    _draw_footer(draw, category, date_label)
    img.save(output_path, "PNG", optimize=True)
    return output_path


def install(pipeline_module: Any) -> Any:
    """Install the no-extra-API impact hierarchy renderer after Run180."""
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
    pipeline_module.RUN181_EYECATCH_IMPACT_HIERARCHY = True
    pipeline_module.RUN181_EYECATCH_BACKGROUND_UNCHANGED = True
    return pipeline_module
