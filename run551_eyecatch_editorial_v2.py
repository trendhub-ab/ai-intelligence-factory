"""Run551: zero-provider editorial eyecatch V2 art direction.

This layer is intentionally presentation-only. It preserves the validated headline
copy and publication metadata, adds no provider/model request, and never changes
Run180 semantic validation.  The renderer turns the approved AI Intelligence Factory
system into a stronger note thumbnail:

* roughly two-thirds copy / one-third symbolic visual;
* one compact ``INSIGHT｜...`` reader hook instead of badge + hook duplication;
* a smaller grammatical lead line and a stronger impact line when the copy supports it;
* orange reserved for the semantic keyword while a generic impact suffix can stay navy;
* subtle background depth plus a larger AI -> decision -> action/robotics motif.

Pillow and renderer modules are imported lazily so pure policy/guard imports remain
zero-Pillow compatible.
"""
from __future__ import annotations

import re
from typing import Any


TEXT_ZONE_RATIO = 0.64
VISUAL_ZONE_RATIO = 0.36
LEAD_TITLE_SCALE = 0.68
IMPACT_TITLE_SCALE = 1.12
BACKGROUND_DEPTH_ALPHA = 0.06

_LEFT = 48
_INSIGHT_TOP = 142
_TITLE_TOP = 220
_FOOTER_TOP = 625
_LEAD_MAX_FONT = 50
_IMPACT_MAX_FONT = 78
_THREE_LINE_MAX_FONT = 66
_TITLE_MIN_FONT = 46
_TITLE_LINE_GAP = 12

# Only noun-like generic endings are split for orange-keyword/navy-suffix rendering.
# Verb/object grammar such as ``舵を切った理由`` remains one semantic highlight.
_SAFE_NAVY_SUFFIXES = (
    "の衝撃",
    "の転換",
    "の変化",
    "の意味",
    "の正体",
    "の本質",
    "の現在地",
    "の未来",
)

_LEAD_ENDINGS = (
    "が示す",
    "を示す",
    "が語る",
    "を語る",
    "から見る",
    "でわかる",
    "とは",
    "を発表",
    "を公開",
)


def split_impact_phrase(text: str) -> tuple[str, str]:
    """Split a Japanese impact phrase at its last useful grammatical connector.

    This helper expresses the art-direction contract; the renderer applies a narrower
    safe-suffix policy before changing color so approved semantic highlights are not
    accidentally fragmented.
    """
    value = str(text or "").strip()
    if len(value) < 4:
        return value, ""
    candidates: list[tuple[str, str]] = []
    for match in re.finditer(r"[のがをへにでと]", value):
        index = match.start()
        left, right = value[:index], value[index:]
        if len(left) >= 2 and len(right) >= 2:
            candidates.append((left, right))
    return candidates[-1] if candidates else (value, "")


def compose_insight(hook: str) -> str:
    value = str(hook or "").strip()
    value = re.sub(r"^INSIGHT\s*[｜|:]\s*", "", value, flags=re.I).strip()
    return f"INSIGHT｜{value}" if value else "INSIGHT｜いま、何が重要なのか？"


def _blend_to_white(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, float(alpha)))
    return tuple(int(round(255 * (1.0 - amount) + channel * amount)) for channel in color)


def _looks_like_lead(line: str, lines: list[str], highlight_text: str | None) -> bool:
    value = str(line or "").strip()
    if len(lines) < 2 or not value:
        return False
    if any(value.endswith(ending) for ending in _LEAD_ENDINGS):
        return True
    if highlight_text and highlight_text not in value and len(value) <= 14:
        return True
    return False


def _safe_accent_runs(line: str, highlight_text: str | None) -> list[tuple[str, bool]]:
    """Return text runs where True means restrained orange emphasis."""
    value = str(line or "")
    for suffix in _SAFE_NAVY_SUFFIXES:
        if value.endswith(suffix) and len(value) > len(suffix) + 1:
            return [(value[: -len(suffix)], True), (suffix, False)]

    highlight = str(highlight_text or "")
    if highlight and value.count(highlight) == 1:
        start = value.find(highlight)
        runs: list[tuple[str, bool]] = []
        if start:
            runs.append((value[:start], False))
        runs.append((highlight, True))
        end = start + len(highlight)
        if end < len(value):
            runs.append((value[end:], False))
        return runs
    return [(value, False)]


def _fit_font_size(draw: Any, ee: Any, text: str, desired: int, max_width: int) -> int:
    for size in range(max(_TITLE_MIN_FONT, int(desired)), _TITLE_MIN_FONT - 1, -1):
        font = ee._jp_font(size, bold=True)
        if ee._text_width(draw, text, font) <= max_width:
            return size
    return _TITLE_MIN_FONT


def _draw_background_depth(draw: Any, ee: Any, accent: tuple[int, int, int]) -> None:
    visual_left = int(round(ee.WIDTH * TEXT_ZONE_RATIO))
    # A white editorial field with just enough depth to stop the right third feeling empty.
    for band in range(8):
        x0 = visual_left + int((ee.WIDTH - visual_left) * band / 8)
        x1 = visual_left + int((ee.WIDTH - visual_left) * (band + 1) / 8)
        alpha = BACKGROUND_DEPTH_ALPHA * (0.45 + 0.55 * (band + 1) / 8)
        draw.rectangle((x0, 94, x1 + 1, ee.HEIGHT), fill=_blend_to_white(accent, alpha))

    grid = _blend_to_white(accent, 0.13)
    for x in range(visual_left + 26, ee.WIDTH, 54):
        draw.line((x, 116, x, 604), fill=grid, width=1)
    for y in range(130, 605, 54):
        draw.line((visual_left + 10, y, ee.WIDTH, y), fill=grid, width=1)


def _draw_arrow(draw: Any, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int]) -> None:
    x0, y0 = start
    x1, y1 = end
    draw.line((x0, y0, x1, y1), fill=color, width=4)
    # The production motif is near-vertical/diagonal; this small symmetric arrowhead is enough.
    draw.polygon([(x1, y1), (x1 - 10, y1 - 5), (x1 - 5, y1 - 14)], fill=color)


def _draw_symbolic_ai_flow(draw: Any, ee: Any, accent: tuple[int, int, int]) -> None:
    """Large abstract AI -> judgement -> action motif for the visual third."""
    navy = (7, 30, 66)
    pale = _blend_to_white(accent, 0.12)
    pale2 = _blend_to_white(accent, 0.20)
    line = _blend_to_white(accent, 0.42)

    # AI core / chip card.
    draw.rounded_rectangle((894, 160, 1098, 286), radius=28, fill=(255, 255, 255), outline=pale2, width=3)
    draw.rounded_rectangle((944, 190, 1048, 256), radius=18, fill=pale, outline=accent, width=3)
    ai_font = ee._latin_font(24, bold=True)
    ai_w = ee._text_width(draw, "AI", ai_font)
    draw.text((996 - ai_w // 2, 209), "AI", font=ai_font, fill=navy)
    for y in (181, 211, 241, 271):
        draw.line((914, y, 936, y), fill=line, width=3)
        draw.line((1056, y, 1078, y), fill=line, width=3)

    # Decision diamond.
    decision_center = (1125, 346)
    draw.polygon([(1125, 292), (1190, 346), (1125, 400), (1060, 346)], fill=(255, 255, 255), outline=pale2)
    draw.ellipse((1102, 323, 1148, 369), fill=pale, outline=accent, width=3)
    draw.line((1114, 346, 1123, 356), fill=navy, width=4)
    draw.line((1123, 356, 1138, 337), fill=navy, width=4)

    # Action / robot terminal. Deliberately iconic, not a humanoid stock illustration.
    draw.rounded_rectangle((938, 438, 1120, 560), radius=26, fill=(255, 255, 255), outline=pale2, width=3)
    draw.rounded_rectangle((972, 459, 1086, 515), radius=18, fill=pale, outline=accent, width=3)
    draw.ellipse((996, 478, 1008, 490), fill=navy)
    draw.ellipse((1050, 478, 1062, 490), fill=navy)
    draw.line((1029, 515, 1029, 540), fill=line, width=4)
    draw.line((985, 540, 1073, 540), fill=line, width=4)
    draw.line((938, 484, 910, 503), fill=line, width=5)
    draw.line((1120, 484, 1148, 503), fill=line, width=5)

    _draw_arrow(draw, (1034, 276), (1098, 313), accent)
    _draw_arrow(draw, (1100, 393), (1060, 438), accent)

    # A few restrained nodes make the system feel connected without becoming a flowchart wall.
    for x, y, radius in ((876, 220, 7), (1212, 252, 6), (1198, 468, 8), (878, 510, 6)):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 255, 255), outline=line, width=2)
    draw.line((883, 220, 925, 220), fill=line, width=2)
    draw.line((1184, 346, 1212, 258), fill=line, width=2)
    draw.line((1120, 506, 1190, 470), fill=line, width=2)


def _draw_insight(draw: Any, ee: Any, hook: str, accent: tuple[int, int, int], text_right: int) -> None:
    prefix = "INSIGHT"
    prefix_font = ee._latin_font(18, bold=True)
    hook_font = ee._jp_font(27, bold=True)
    prefix_w = ee._text_width(draw, prefix, prefix_font)
    draw.text((_LEFT, _INSIGHT_TOP + 6), prefix, font=prefix_font, fill=accent)
    sep_x = _LEFT + prefix_w + 13
    draw.line((sep_x, _INSIGHT_TOP + 5, sep_x, _INSIGHT_TOP + 31), fill=_blend_to_white(accent, 0.40), width=2)
    text = compose_insight(hook).split("｜", 1)[1]
    draw.text((sep_x + 15, _INSIGHT_TOP), text, font=hook_font, fill=(7, 30, 66))
    draw.rounded_rectangle((_LEFT, _INSIGHT_TOP + 42, min(text_right, sep_x + 15 + ee._text_width(draw, text, hook_font)), _INSIGHT_TOP + 46), radius=2, fill=_blend_to_white(accent, 0.20))


def _draw_runs(
    draw: Any,
    ee: Any,
    r181: Any,
    runs: list[tuple[str, bool]],
    size: int,
    x: int,
    top: int,
    ink_runs: list[Any],
) -> int:
    font = ee._jp_font(size, bold=True)
    bbox_all = draw.textbbox((0, 0), "".join(text for text, _ in runs), font=font)
    line_height = max(0, bbox_all[3] - bbox_all[1])
    cursor = x
    for text, emphasized in runs:
        if not text:
            continue
        bbox = draw.textbbox((0, 0), text, font=font)
        visible_height = max(0, bbox[3] - bbox[1])
        draw_y = top + (line_height - visible_height) - bbox[1]
        color = r181.HIGHLIGHT_ORANGE if emphasized else r181.TITLE_NAVY
        draw.text((cursor, draw_y), text, font=font, fill=color)
        ink_runs.append((text, font, cursor, draw_y, color))
        cursor += ee._text_width(draw, text, font)
    return line_height


def _render_editorial_v2(
    title: str,
    summary: str,
    output_path: str,
    validated: dict[str, Any],
    category: str | None = None,
    date_label: str | None = None,
    *,
    highlight_text: str | None = None,
) -> str:
    import os

    from PIL import Image, ImageDraw

    import editorial_eyecatch as ee
    import eyecatch_publication_contract as headline_contract
    import run181_eyecatch_visual_balance as r181

    category = (category or ee.infer_editorial_category(title, summary)).strip() or "AI & TECH"
    accent = ee._CATEGORY_ACCENTS.get(category, ee._CATEGORY_ACCENTS["AI & TECH"])
    date_label = date_label or ee.datetime.now(ee.ZoneInfo("Asia/Tokyo")).strftime("%Y.%m")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    image = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (253, 254, 255))
    draw = ImageDraw.Draw(image)

    _draw_background_depth(draw, ee, accent)
    _draw_symbolic_ai_flow(draw, ee, accent)
    ee._draw_brand(draw, accent)
    ee._draw_tags(draw, category, date_label, accent)

    hook = r181._editorial_hook(title, summary, category)
    text_right = int(round(ee.WIDTH * TEXT_ZONE_RATIO))
    _draw_insight(draw, ee, hook, accent, text_right)

    title_lines = [str(line).strip() for line in validated.get("title_lines", []) if str(line).strip()]
    if not title_lines:
        raise ValueError("eyecatch title lines are required")
    expected_headline = str(validated.get("eyecatch_title") or ee.editorial_hook_from_title(title))
    proof = headline_contract.headline_pnginfo(title, expected_headline, title_lines)

    max_width = max(320, text_right - _LEFT - 12)
    lead_first = _looks_like_lead(title_lines[0], title_lines, highlight_text)
    y = _TITLE_TOP
    ink_runs: list[Any] = []

    for index, line in enumerate(title_lines):
        is_lead = bool(index == 0 and lead_first)
        if is_lead:
            desired = int(round(_IMPACT_MAX_FONT * LEAD_TITLE_SCALE))
            size = _fit_font_size(draw, ee, line, min(_LEAD_MAX_FONT, desired), max_width)
            runs = [(line, False)]
        else:
            ceiling = _THREE_LINE_MAX_FONT if len(title_lines) >= 3 else _IMPACT_MAX_FONT
            desired = min(ceiling, int(round(70 * IMPACT_TITLE_SCALE)))
            size = _fit_font_size(draw, ee, line, desired, max_width)
            runs = _safe_accent_runs(line, highlight_text if index == len(title_lines) - 1 else None)

        height = _draw_runs(draw, ee, r181, runs, size, _LEFT, y, ink_runs)
        y += height + (_TITLE_LINE_GAP + (7 if is_lead else 0))

    # Preserve the established compact footer contract while keeping all middle space clean.
    r181._draw_footer(draw, category, date_label)
    headline_contract.bind_headline_pixels(image, proof, ink_runs)
    image.save(output_path, "PNG", optimize=True, pnginfo=proof)
    return output_path


def install(pipeline_module: Any) -> Any:
    """Install the final deterministic art-direction renderer without touching Run180."""
    if getattr(pipeline_module, "_RUN551_EYECATCH_EDITORIAL_V2_INSTALLED", False):
        return pipeline_module

    import run181_eyecatch_visual_balance as r181

    original_renderer = r181._render_balanced_plan

    def editorial_v2_renderer(
        title: str,
        summary: str,
        output_path: str,
        validated: dict[str, Any],
        category: str | None = None,
        date_label: str | None = None,
        *,
        highlight_text: str | None = None,
    ) -> str:
        return _render_editorial_v2(
            title,
            summary,
            output_path,
            validated,
            category=category,
            date_label=date_label,
            highlight_text=highlight_text,
        )

    editorial_v2_renderer._run551_original_renderer = original_renderer  # type: ignore[attr-defined]
    r181._render_balanced_plan = editorial_v2_renderer

    pipeline_module._RUN551_EYECATCH_EDITORIAL_V2_INSTALLED = True
    pipeline_module.RUN551_EXTRA_PROVIDER_CALLS = 0
    pipeline_module.RUN551_TEXT_ZONE_RATIO = TEXT_ZONE_RATIO
    pipeline_module.RUN551_VISUAL_ZONE_RATIO = VISUAL_ZONE_RATIO
    pipeline_module.RUN551_BADGE_REMOVED = True
    pipeline_module.RUN551_SINGLE_INSIGHT_LINE = True
    return pipeline_module
