"""Run551: approved-raster editorial eyecatch V2.

Presentation-only, zero-provider rendering layer for AI Intelligence Factory.
Run180 continues to own semantic/layout validation. Run551 uses the user-approved
AI background as the immutable visual source and deterministically overlays only the
brand, metadata, insight hook, validated title and footer.

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

_LEFT = 48
_INSIGHT_TOP = 142
_TITLE_TOP = 220
_LEAD_MAX_FONT = 50
_IMPACT_MAX_FONT = 78
_THREE_LINE_MAX_FONT = 66
_TITLE_MIN_FONT = 46
_TITLE_LINE_GAP = 12

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
    value = str(hook or "").strip()
    value = re.sub(r"^INSIGHT\s*[｜|:]\s*", "", value, flags=re.I).strip()
    return f"INSIGHT｜{value}" if value else "INSIGHT｜いま、何が重要なのか？"


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
    except Exception as exc:  # binascii.Error is deliberately normalized to one fail-closed contract.
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


def _draw_insight(draw: Any, ee: Any, hook: str, accent: tuple[int, int, int], text_right: int) -> None:
    prefix = "INSIGHT"
    prefix_font = ee._latin_font(18, bold=True)
    hook_font = ee._jp_font(27, bold=True)
    prefix_w = ee._text_width(draw, prefix, prefix_font)
    draw.text((_LEFT, _INSIGHT_TOP + 6), prefix, font=prefix_font, fill=accent)
    sep_x = _LEFT + prefix_w + 13
    draw.line(
        (sep_x, _INSIGHT_TOP + 5, sep_x, _INSIGHT_TOP + 31),
        fill=_blend_to_white(accent, 0.40),
        width=2,
    )
    text = compose_insight(hook).split("｜", 1)[1]
    draw.text((sep_x + 15, _INSIGHT_TOP), text, font=hook_font, fill=(7, 30, 66))
    draw.rounded_rectangle(
        (
            _LEFT,
            _INSIGHT_TOP + 42,
            min(text_right, sep_x + 15 + ee._text_width(draw, text, hook_font)),
            _INSIGHT_TOP + 46,
        ),
        radius=2,
        fill=_blend_to_white(accent, 0.20),
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

    # The approved raster is the complete visual field. Only deterministic typography
    # is layered on top; no synthetic visual element is redrawn here.
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
            runs = _safe_accent_runs(
                line,
                highlight_text if index == len(title_lines) - 1 else None,
            )

        height = _draw_runs(draw, ee, r181, runs, size, _LEFT, y, ink_runs)
        y += height + (_TITLE_LINE_GAP + (7 if is_lead else 0))

    r181._draw_footer(draw, category, date_label)
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
    pipeline_module.RUN551_BADGE_REMOVED = True
    pipeline_module.RUN551_SINGLE_INSIGHT_LINE = True
    pipeline_module.RUN551_BACKGROUND_MASTER_SHA256 = BACKGROUND_MASTER_SHA256
    return pipeline_module
