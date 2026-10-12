"""Run551: zero-provider editorial eyecatch V2 art direction.

This layer is intentionally presentation-only. It preserves the validated headline
copy and publication metadata, adds no provider/model request, and never changes
Run180 semantic validation. The renderer turns the approved AI Intelligence Factory
system into a stronger note thumbnail:

* roughly two-thirds copy / one-third symbolic visual;
* one compact ``INSIGHT｜...`` reader hook instead of badge + hook duplication;
* a smaller grammatical lead line and a stronger impact line when the copy supports it;
* orange reserved for the semantic keyword while a generic impact suffix can stay navy;
* subtle background depth plus a premium glass AI-core -> action motif.

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


def visual_motif_contract() -> dict[str, object]:
    """Stable art-direction contract for the robotics reference composition."""
    return {
        "style": "isometric-glass-ai-core",
        "flow": "ai-core-to-motion-control",
        "action_symbol": "industrial-robot-arm",
        "humanoid_face": False,
        "warm_accent": "restrained-orange",
    }


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
    # Keep the left editorial field pristine; the visual third gets only a low-contrast wash.
    for band in range(8):
        x0 = visual_left + int((ee.WIDTH - visual_left) * band / 8)
        x1 = visual_left + int((ee.WIDTH - visual_left) * (band + 1) / 8)
        alpha = BACKGROUND_DEPTH_ALPHA * (0.40 + 0.60 * (band + 1) / 8)
        draw.rectangle((x0, 94, x1 + 1, ee.HEIGHT), fill=_blend_to_white(accent, alpha))

    # Sparse circuit traces instead of a diagram-like full grid.
    trace = _blend_to_white(accent, 0.16)
    for y, x0, x1 in ((168, visual_left + 34, 1218), (302, visual_left + 78, 1250), (516, visual_left + 24, 1194)):
        draw.line((x0, y, x1, y), fill=trace, width=1)
    for x, y0, y1 in ((866, 136, 238), (1218, 168, 280), (1194, 454, 548)):
        draw.line((x, y0, x, y1), fill=trace, width=1)


def _draw_arrow(draw: Any, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int]) -> None:
    x0, y0 = start
    x1, y1 = end
    draw.line((x0, y0, x1, y1), fill=color, width=3)
    draw.polygon([(x1, y1), (x1 - 9, y1 - 4), (x1 - 5, y1 - 12)], fill=color)


def _draw_glass_plate(
    draw: Any,
    points: list[tuple[int, int]],
    *,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    offset: int = 8,
) -> None:
    """Draw a pseudo-isometric glass slab with a visible lower edge."""
    lower = [(x, y + offset) for x, y in points]
    draw.polygon(lower, fill=_blend_to_white(outline, 0.16), outline=_blend_to_white(outline, 0.30))
    draw.polygon(points, fill=fill, outline=outline)
    draw.line((points[2][0], points[2][1], lower[2][0], lower[2][1]), fill=outline, width=2)
    draw.line((points[3][0], points[3][1], lower[3][0], lower[3][1]), fill=outline, width=2)


def _draw_industrial_robot_arm(
    draw: Any,
    accent: tuple[int, int, int],
    navy: tuple[int, int, int],
    warm: tuple[int, int, int],
) -> None:
    """Draw a compact industrial arm: base, two links, elbow, wrist and gripper."""
    pale = _blend_to_white(accent, 0.24)
    structure = _blend_to_white(accent, 0.52)

    # Base / pedestal.
    draw.rounded_rectangle((1078, 526, 1170, 548), radius=9, fill=_blend_to_white(accent, 0.18), outline=structure, width=2)
    draw.rounded_rectangle((1100, 493, 1148, 532), radius=10, fill=(255, 255, 255), outline=accent, width=3)

    # Link geometry is intentionally machine-like rather than humanoid.
    base_joint = (1124, 493)
    elbow = (1065, 440)
    wrist = (1122, 382)
    tool = (1176, 405)
    draw.line((*base_joint, *elbow), fill=pale, width=18)
    draw.line((*base_joint, *elbow), fill=accent, width=5)
    draw.line((*elbow, *wrist), fill=pale, width=16)
    draw.line((*elbow, *wrist), fill=accent, width=5)
    draw.line((*wrist, *tool), fill=pale, width=14)
    draw.line((*wrist, *tool), fill=navy, width=4)

    for x, y, outer, inner in (
        (*base_joint, 14, 6),
        (*elbow, 15, 6),
        (*wrist, 12, 5),
    ):
        draw.ellipse((x - outer, y - outer, x + outer, y + outer), fill=(255, 255, 255), outline=structure, width=3)
        draw.ellipse((x - inner, y - inner, x + inner, y + inner), fill=accent)

    # Restrained orange is a single control/action cue at the tool point.
    draw.ellipse((tool[0] - 7, tool[1] - 7, tool[0] + 7, tool[1] + 7), fill=warm, outline=(255, 255, 255), width=2)
    draw.line((1181, 400, 1203, 390), fill=navy, width=4)
    draw.line((1181, 410, 1204, 420), fill=navy, width=4)

    # Motion arcs make the symbol read as controlled movement, not a static appliance.
    arc = _blend_to_white(accent, 0.42)
    draw.arc((1022, 397, 1100, 475), 205, 310, fill=arc, width=2)
    draw.arc((1082, 350, 1160, 426), 210, 322, fill=arc, width=2)


def _draw_abstract_output(draw: Any, accent: tuple[int, int, int], navy: tuple[int, int, int]) -> None:
    """Neutral action symbol for non-robotics categories."""
    pale = _blend_to_white(accent, 0.18)
    line = _blend_to_white(accent, 0.48)
    for index, (x, y) in enumerate(((1035, 420), (1092, 454), (1149, 488))):
        draw.rounded_rectangle((x, y, x + 78, y + 54), radius=13, fill=(255, 255, 255), outline=line, width=2)
        draw.rounded_rectangle((x + 14, y + 13, x + 64, y + 25), radius=5, fill=pale)
        draw.line((x + 16, y + 37, x + 48 + index * 4, y + 37), fill=navy, width=3)


def _draw_symbolic_ai_flow(
    draw: Any,
    ee: Any,
    accent: tuple[int, int, int],
    category: str = "AI & TECH",
) -> None:
    """Premium glass AI core feeding an action symbol in the visual third."""
    navy = (7, 30, 66)
    warm = (240, 111, 45)
    glass_edge = _blend_to_white(accent, 0.52)
    glass_mid = _blend_to_white(accent, 0.16)
    glass_light = _blend_to_white(accent, 0.09)
    signal = _blend_to_white(accent, 0.60)

    # Three offset pseudo-isometric glass plates create depth without raster assets.
    plates = (
        [(887, 274), (1003, 218), (1152, 283), (1034, 343)],
        [(904, 244), (1016, 190), (1141, 246), (1028, 302)],
        [(929, 214), (1024, 168), (1117, 210), (1021, 257)],
    )
    _draw_glass_plate(draw, plates[0], fill=glass_light, outline=_blend_to_white(accent, 0.28), offset=11)
    _draw_glass_plate(draw, plates[1], fill=glass_mid, outline=_blend_to_white(accent, 0.38), offset=9)
    _draw_glass_plate(draw, plates[2], fill=_blend_to_white(accent, 0.22), outline=glass_edge, offset=7)

    # Central compute core and a faint halo.
    core_x, core_y = 1023, 218
    for radius, alpha in ((45, 0.08), (34, 0.13), (25, 0.20)):
        halo = _blend_to_white(accent, alpha)
        draw.ellipse((core_x - radius, core_y - radius, core_x + radius, core_y + radius), fill=halo)
    draw.rounded_rectangle((987, 190, 1059, 246), radius=14, fill=(255, 255, 255), outline=accent, width=3)
    draw.rounded_rectangle((1001, 201, 1045, 235), radius=9, fill=_blend_to_white(accent, 0.28), outline=glass_edge, width=2)
    ai_font = ee._latin_font(17, bold=True)
    ai_w = ee._text_width(draw, "AI", ai_font)
    draw.text((core_x - ai_w // 2, 207), "AI", font=ai_font, fill=navy)

    # Circuit pins/nodes arranged around the glass stack.
    for x0, y0, x1, y1 in (
        (952, 206, 904, 183),
        (1088, 226, 1177, 265),
        (965, 286, 889, 324),
        (1082, 302, 1176, 338),
    ):
        draw.line((x0, y0, x1, y1), fill=signal, width=2)
        draw.ellipse((x1 - 5, y1 - 5, x1 + 5, y1 + 5), fill=(255, 255, 255), outline=glass_edge, width=2)

    # A motion-control signal leaves the compute stack; one warm node is enough.
    control_node = (1014, 350)
    draw.line((1024, 306, *control_node), fill=signal, width=3)
    draw.ellipse((1007, 343, 1021, 357), fill=warm, outline=(255, 255, 255), width=2)
    draw.line((*control_node, 1078, 389), fill=signal, width=3)

    if str(category or "").strip().upper() == "ROBOTICS":
        _draw_industrial_robot_arm(draw, accent, navy, warm)
    else:
        _draw_abstract_output(draw, accent, navy)


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
    _draw_symbolic_ai_flow(draw, ee, accent, category)
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
