"""Run551: approved-raster editorial eyecatch V2.

Presentation-only, zero-provider rendering layer for AI Intelligence Factory.
Run180 continues to own semantic/layout validation. Run551 uses the user-approved
AI background as the immutable visual source and deterministically overlays only the
brand, metadata, dynamic reader-purpose badge, editorial hook, validated title and footer.

The approved 1536x804 source has the same aspect ratio as the 1280x670 note canvas.
The committed production master is therefore a straight 1280x670 downscale with no
crop and no synthetic redraw. It is stored as six base64 text parts because the
repository connector cannot write binary assets directly; the decoded bytes are
SHA-256 pinned and fail closed.
"""
from __future__ import annotations

import base64
import hashlib
import io
import re
from pathlib import Path
from typing import Any


TEXT_ZONE_RATIO = 0.64
VISUAL_ZONE_RATIO = 0.36
LEAD_TITLE_SCALE = 0.68
IMPACT_TITLE_SCALE = 1.12

BACKGROUND_MASTER_SOURCE_SIZE = (1536, 804)
BACKGROUND_MASTER_TARGET_SIZE = (1280, 670)
BACKGROUND_MASTER_SHA256 = "5f1ab5f8ddc807825ad8fa29fdb96b5a165742af73b779223b7fccf8547a77fd"
BACKGROUND_MASTER_FORMAT = "WEBP"
_BACKGROUND_PARTS_RELATIVE = Path("assets") / "eyecatch" / "v2" / ".background_master_parts"
_BACKGROUND_PART_NAMES = tuple(f"part{index:02d}.b64" for index in range(1, 7))

# 1280x670 coordinates measured from the user-approved 1536x804 sample.
_LEFT = 48
_BADGE_TOP = 140
_BADGE_HEIGHT = 44
_HOOK_TOP = 204
_TITLE_TOP = 310
_FOOTER_TOP = 592
_BRAND_FONT = 32
_BADGE_FONT = 24
_HOOK_FONT = 33
_LEAD_TITLE_FONT = 74
_IMPACT_TITLE_FONT = 85
_FOOTER_FONT = 19
_LEAD_TITLE_LEFT = 45
_IMPACT_TITLE_LEFT = 42
_THREE_LINE_MAX_FONT = 66
_TITLE_MIN_FONT = 46
_TITLE_LINE_GAP = 8

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
    """Split a Japanese impact phrase at its last useful grammatical connector."""
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
    """Compatibility helper retained for callers from the pre-badge V2 prototype."""
    value = str(hook or "").strip()
    value = re.sub(r"^INSIGHT\s*[｜|:]\s*", "", value, flags=re.I).strip()
    return f"INSIGHT｜{value}" if value else "INSIGHT｜いま、何が重要なのか？"


def select_badge(title: str, summary: str, category: str) -> str:
    """Choose the reader-purpose badge from existing deterministic article cues."""
    import eyecatch_badge_taxonomy as badge_taxonomy

    return badge_taxonomy.classify_badge(title, summary, category)


def editorial_layout_contract() -> dict[str, int]:
    """Expose the sample-aligned geometry for regression tests."""
    return {
        "left": _LEFT,
        "badge_top": _BADGE_TOP,
        "badge_height": _BADGE_HEIGHT,
        "hook_top": _HOOK_TOP,
        "title_top": _TITLE_TOP,
        "footer_top": _FOOTER_TOP,
    }


def typography_contract() -> dict[str, int]:
    """Expose the measured sample typography scale for regression tests."""
    return {
        "brand_font": _BRAND_FONT,
        "badge_font": _BADGE_FONT,
        "hook_font": _HOOK_FONT,
        "lead_title_font": _LEAD_TITLE_FONT,
        "impact_title_font": _IMPACT_TITLE_FONT,
        "footer_font": _FOOTER_FONT,
        "lead_title_left": _LEAD_TITLE_LEFT,
        "impact_title_left": _IMPACT_TITLE_LEFT,
        "title_line_gap": _TITLE_LINE_GAP,
    }


def background_master_contract() -> dict[str, object]:
    """Return the pinned source-of-truth contract for the approved raster background."""
    return {
        "path": "assets/eyecatch/v2/.background_master_parts",
        "source_size": BACKGROUND_MASTER_SOURCE_SIZE,
        "target_size": BACKGROUND_MASTER_TARGET_SIZE,
        "sha256": BACKGROUND_MASTER_SHA256,
        "format": BACKGROUND_MASTER_FORMAT,
        "part_count": len(_BACKGROUND_PART_NAMES),
        "synthetic_visual": False,
        "crop_required": False,
    }


def _background_master_bytes() -> bytes:
    """Decode and checksum the approved production background, failing closed."""
    root = Path(__file__).resolve().parent
    parts_dir = root / _BACKGROUND_PARTS_RELATIVE
    encoded_parts: list[str] = []
    for name in _BACKGROUND_PART_NAMES:
        path = parts_dir / name
        if not path.is_file():
            raise RuntimeError(f"background master part is missing: {path.relative_to(root)}")
        try:
            encoded_parts.append(path.read_text(encoding="ascii").strip())
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"background master part is unreadable: {path.relative_to(root)}") from exc

    try:
        payload = base64.b64decode("".join(encoded_parts), validate=True)
    except Exception as exc:
        raise RuntimeError("background master base64 is invalid") from exc

    actual = hashlib.sha256(payload).hexdigest()
    if actual != BACKGROUND_MASTER_SHA256:
        raise RuntimeError(
            "background master checksum mismatch: "
            f"expected={BACKGROUND_MASTER_SHA256} actual={actual}"
        )
    return payload


def _load_background_master(ee: Any):
    from PIL import Image

    try:
        with Image.open(io.BytesIO(_background_master_bytes())) as source:
            if source.format != BACKGROUND_MASTER_FORMAT:
                raise RuntimeError(
                    f"background master format mismatch: expected={BACKGROUND_MASTER_FORMAT} actual={source.format}"
                )
            image = source.convert("RGB")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("background master image is invalid") from exc

    expected_size = (ee.WIDTH, ee.HEIGHT)
    if image.size != expected_size or image.size != BACKGROUND_MASTER_TARGET_SIZE:
        raise RuntimeError(
            f"background master size mismatch: expected={expected_size} actual={image.size}"
        )
    return image


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


def _draw_brand(draw: Any, ee: Any, accent: tuple[int, int, int]) -> None:
    """Draw the brand at the normalized position/scale of the approved sample."""
    x0, baseline = 50, 97
    heights = (18, 27, 38, 47)
    fills = (
        accent,
        (32, 93, 155),
        (17, 69, 126),
        (10, 35, 73),
    )
    for index, height in enumerate(heights):
        x = x0 + index * 14
        draw.rectangle((x, baseline - height, x + 10, baseline), fill=fills[index])
    draw.text((125, 58), ee.BRAND_NAME, font=ee._latin_font(_BRAND_FONT, bold=True), fill=(10, 35, 73))


def _draw_tags(draw: Any, ee: Any, category: str, date_label: str, accent: tuple[int, int, int]) -> None:
    """Keep the top-right metadata aligned with the approved sample."""
    tag_font = ee._latin_font(24, bold=True)
    date_font = ee._latin_font(23, bold=True)
    category_w = ee._text_width(draw, category, tag_font) + 48
    date_w = ee._text_width(draw, date_label, date_font) + 40
    gap = 14
    right = ee.WIDTH - 44
    date_box = (right - date_w, 51, right, 98)
    category_box = (date_box[0] - gap - category_w, 51, date_box[0] - gap, 98)
    draw.rounded_rectangle(category_box, radius=9, fill=accent)
    draw.rounded_rectangle(date_box, radius=9, fill=(252, 253, 255), outline=(198, 210, 228), width=2)
    draw.text((category_box[0] + 24, 62), category, font=tag_font, fill=(255, 255, 255))
    draw.text((date_box[0] + 20, 62), date_label, font=date_font, fill=(15, 35, 70))


def _draw_badge(draw: Any, ee: Any, label: str, accent: tuple[int, int, int]) -> None:
    import eyecatch_badge_taxonomy as badge_taxonomy

    font = ee._jp_font(_BADGE_FONT, bold=True)
    text_w = ee._text_width(draw, label, font)
    x0, y0 = _LEFT, _BADGE_TOP
    x1, y1 = x0 + text_w + 72, y0 + _BADGE_HEIGHT
    fill = _blend_to_white(accent, 0.11)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=_BADGE_HEIGHT // 2, fill=fill)
    badge_taxonomy.draw_badge_icon(draw, label, x0 + 12, y0 + 9, accent, size=26)
    bbox = draw.textbbox((0, 0), label, font=font)
    visible_height = max(0, bbox[3] - bbox[1])
    text_y = y0 + (_BADGE_HEIGHT - visible_height) // 2 - bbox[1]
    draw.text((x0 + 50, text_y), label, font=font, fill=(7, 30, 66))


def _draw_hook(draw: Any, ee: Any, hook: str, accent: tuple[int, int, int], text_right: int) -> None:
    font = ee._jp_font(_HOOK_FONT, bold=True)
    bbox = draw.textbbox((0, 0), hook, font=font)
    text_w = max(0, bbox[2] - bbox[0])
    draw.text((_LEFT, _HOOK_TOP - bbox[1]), hook, font=font, fill=(7, 30, 66))
    underline_right = min(text_right, _LEFT + text_w + 18)
    draw.rounded_rectangle(
        (_LEFT, _HOOK_TOP + 39, underline_right, _HOOK_TOP + 45),
        radius=3,
        fill=_blend_to_white(accent, 0.17),
    )


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


def _draw_footer(draw: Any, ee: Any, category: str, date_label: str) -> None:
    label_font = ee._jp_font(_FOOTER_FONT, bold=True)
    date_font = ee._latin_font(_FOOTER_FONT, bold=True)
    label = f"{category} / 解説"
    draw.text((_LEFT, _FOOTER_TOP), label, font=label_font, fill=(18, 42, 79))
    label_w = ee._text_width(draw, label, label_font)
    divider_x = _LEFT + label_w + 26
    draw.line(
        (divider_x, _FOOTER_TOP - 1, divider_x, _FOOTER_TOP + 25),
        fill=(185, 201, 222),
        width=2,
    )
    draw.text((divider_x + 24, _FOOTER_TOP), date_label, font=date_font, fill=(18, 42, 79))


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

    from PIL import ImageDraw

    import editorial_eyecatch as ee
    import eyecatch_publication_contract as headline_contract
    import run181_eyecatch_visual_balance as r181

    category = (category or ee.infer_editorial_category(title, summary)).strip() or "AI & TECH"
    accent = ee._CATEGORY_ACCENTS.get(category, ee._CATEGORY_ACCENTS["AI & TECH"])
    date_label = date_label or ee.datetime.now(ee.ZoneInfo("Asia/Tokyo")).strftime("%Y.%m")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    image = _load_background_master(ee)
    draw = ImageDraw.Draw(image)

    _draw_brand(draw, ee, accent)
    _draw_tags(draw, ee, category, date_label, accent)

    badge = select_badge(title, summary, category)
    _draw_badge(draw, ee, badge, accent)
    hook = r181._editorial_hook(title, summary, category)
    text_right = int(round(ee.WIDTH * TEXT_ZONE_RATIO))
    _draw_hook(draw, ee, hook, accent, text_right)

    title_lines = [str(line).strip() for line in validated.get("title_lines", []) if str(line).strip()]
    if not title_lines:
        raise ValueError("eyecatch title lines are required")
    expected_headline = str(validated.get("eyecatch_title") or ee.editorial_hook_from_title(title))
    proof = headline_contract.headline_pnginfo(title, expected_headline, title_lines)

    max_width = max(320, text_right - min(_LEAD_TITLE_LEFT, _IMPACT_TITLE_LEFT) - 12)
    lead_first = _looks_like_lead(title_lines[0], title_lines, highlight_text)
    y = _TITLE_TOP
    ink_runs: list[Any] = []

    for index, line in enumerate(title_lines):
        is_lead = bool(index == 0 and lead_first)
        if is_lead:
            size = _fit_font_size(draw, ee, line, _LEAD_TITLE_FONT, max_width)
            runs = [(line, False)]
            x = _LEAD_TITLE_LEFT
        else:
            ceiling = _THREE_LINE_MAX_FONT if len(title_lines) >= 3 else _IMPACT_TITLE_FONT
            desired = min(ceiling, _IMPACT_TITLE_FONT)
            size = _fit_font_size(draw, ee, line, desired, max_width)
            runs = _safe_accent_runs(
                line,
                highlight_text if index == len(title_lines) - 1 else None,
            )
            x = _IMPACT_TITLE_LEFT

        height = _draw_runs(draw, ee, r181, runs, size, x, y, ink_runs)
        y += height + (_TITLE_LINE_GAP + (7 if is_lead else 0))

    _draw_footer(draw, ee, category, date_label)
    headline_contract.bind_headline_pixels(image, proof, ink_runs)
    image.save(output_path, "PNG", optimize=True, pnginfo=proof)
    return output_path


def install(pipeline_module: Any) -> Any:
    """Install the deterministic approved-background renderer without touching Run180."""
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
    pipeline_module.RUN551_BADGE_REMOVED = False
    pipeline_module.RUN551_DYNAMIC_BADGE = True
    pipeline_module.RUN551_SINGLE_INSIGHT_LINE = False
    pipeline_module.RUN551_BACKGROUND_MASTER_SHA256 = BACKGROUND_MASTER_SHA256
    return pipeline_module
