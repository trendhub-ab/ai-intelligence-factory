"""Run178: Gemini-assisted editorial typography for public note eyecatches.

Gemini is used only as a layout director: it may choose line breaks and bounded font sizes,
but it may not rewrite the public headline/subheadline or render image pixels.  The actual
1280x670 image remains deterministic PIL output.  Any provider, JSON, validation, kinsoku,
or geometry failure falls back to the already-approved editorial renderer with no retry.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from PIL import Image, ImageDraw

import editorial_eyecatch as ee


ENABLE_EYECATCH_LAYOUT_OPTIMIZER = os.environ.get(
    "ENABLE_EYECATCH_LAYOUT_OPTIMIZER", "true"
).lower() in {"1", "true", "yes", "on"}
EYECATCH_LAYOUT_MODEL = os.environ.get("EYECATCH_LAYOUT_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"
EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS = max(256, int(os.environ.get("EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS", "700")))

_TITLE_MIN_FONT = 48
_TITLE_MAX_FONT = 82
_SUB_MIN_FONT = 22
_SUB_MAX_FONT = 30
_TITLE_MAX_WIDTH = 760
_SUB_MAX_WIDTH = 725

# Japanese line-breaking prohibitions.  The model chooses semantic breaks; these are the
# deterministic last line of defence so punctuation/small kana never starts a new line.
_FORBIDDEN_LINE_START = set(
    "、。，．・：；？！!?)]）］｝〕〉》」』】〙〗〟’”»ー〜～…‥"
    "ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ"
)
_FORBIDDEN_LINE_END = set("([（［｛〔〈《「『【〘〖〝‘“«")

_LAYOUT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title_lines": {"type": "array", "items": {"type": "string"}},
        "title_font_size": {"type": "integer"},
        "title_line_gap": {"type": "integer"},
        "subheadline_lines": {"type": "array", "items": {"type": "string"}},
        "subheadline_font_size": {"type": "integer"},
    },
    "required": [
        "title_lines",
        "title_font_size",
        "title_line_gap",
        "subheadline_lines",
        "subheadline_font_size",
    ],
}


def _canonical_partition_text(value: str) -> str:
    """Compare model partitions without treating a line break replacing whitespace as a rewrite."""
    return re.sub(r"\s+", "", str(value or ""))


def _coerce_lines(value: Any, max_lines: int) -> list[str] | None:
    if not isinstance(value, list) or not 1 <= len(value) <= max_lines:
        return None
    lines: list[str] = []
    for item in value:
        if not isinstance(item, str) or "\n" in item or "\r" in item:
            return None
        line = item.strip()
        if not line:
            return None
        lines.append(line)
    return lines


def _kinsoku_ok(lines: list[str]) -> bool:
    for index, line in enumerate(lines):
        if not line:
            return False
        if index > 0 and line[0] in _FORBIDDEN_LINE_START:
            return False
        if index < len(lines) - 1 and line[-1] in _FORBIDDEN_LINE_END:
            return False
        # A one-character orphan line is nearly always visually accidental on this card.
        if len(_canonical_partition_text(line)) < 2 and len(lines) > 1:
            return False
    return True


def _fit_requested_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    requested_size: int,
    min_size: int,
    max_size: int,
    max_width: int,
) -> tuple[int, Any] | None:
    try:
        size = int(requested_size)
    except (TypeError, ValueError):
        return None
    size = max(min_size, min(max_size, size))
    for candidate in range(size, min_size - 1, -1):
        font = ee._jp_font(candidate, bold=True)
        if all(ee._text_width(draw, line, font) <= max_width for line in lines):
            return candidate, font
    return None


def validate_layout_plan(headline: str, subheadline: str, plan: Any) -> dict[str, Any] | None:
    """Validate a model plan as typography only; any textual rewrite fails closed."""
    if not isinstance(plan, dict):
        return None

    title_lines = _coerce_lines(plan.get("title_lines"), 3)
    sub_lines = _coerce_lines(plan.get("subheadline_lines"), 2)
    if title_lines is None or sub_lines is None:
        return None
    if _canonical_partition_text("".join(title_lines)) != _canonical_partition_text(headline):
        return None
    if _canonical_partition_text("".join(sub_lines)) != _canonical_partition_text(subheadline):
        return None
    if not _kinsoku_ok(title_lines) or not _kinsoku_ok(sub_lines):
        return None

    try:
        line_gap = int(plan.get("title_line_gap"))
    except (TypeError, ValueError):
        return None
    line_gap = max(6, min(18, line_gap))

    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    title_fit = _fit_requested_lines(
        draw, title_lines, plan.get("title_font_size"), _TITLE_MIN_FONT, _TITLE_MAX_FONT, _TITLE_MAX_WIDTH
    )
    sub_fit = _fit_requested_lines(
        draw, sub_lines, plan.get("subheadline_font_size"), _SUB_MIN_FONT, _SUB_MAX_FONT, _SUB_MAX_WIDTH
    )
    if title_fit is None or sub_fit is None:
        return None

    title_size, _ = title_fit
    sub_size, _ = sub_fit
    return {
        "title_lines": title_lines,
        "title_font_size": title_size,
        "title_line_gap": line_gap,
        "subheadline_lines": sub_lines,
        "subheadline_font_size": sub_size,
    }


def _layout_prompt(headline: str, subheadline: str) -> str:
    payload = json.dumps(
        {"headline": headline, "subheadline": subheadline}, ensure_ascii=False
    )
    return f"""あなたは日本語エディトリアルデザインのタイポグラフィ担当です。
1280x670のnoteアイキャッチで、左側の文字領域を最も読みやすく美しく組んでください。

入力: {payload}

絶対条件:
- 文言は1文字も追加・削除・言い換えしない。改行位置だけを決める。
- headlineは1〜3行、各行の描画幅は760px以内。
- subheadlineは1〜2行、各行の描画幅は725px以内。
- headlineのフォントサイズは48〜82、subheadlineは22〜30。
- headlineの行間は6〜18。
- 日本語の意味のまとまりを優先し、助詞・活用・固有名詞・英単語の途中で不自然に切らない。
- 行頭に句読点、閉じ括弧、長音、三点リーダー、小書き仮名を置かない。
- 行末に開き括弧を置かない。
- 行の長さは機械的な均等割りではなく、意味と視覚バランスの両方で整える。
- 画像、色、文言、カテゴリ、日付には一切触れない。
- JSON以外は返さない。
"""


def _parse_plan_response(response: Any) -> dict[str, Any] | None:
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _render_with_validated_plan(
    title: str,
    summary: str,
    output_path: str,
    validated: dict[str, Any],
    category: str | None = None,
    date_label: str | None = None,
) -> str:
    category = (category or ee.infer_editorial_category(title, summary)).strip() or "AI & TECH"
    accent = ee._CATEGORY_ACCENTS.get(category, ee._CATEGORY_ACCENTS["AI & TECH"])
    date_label = date_label or ee.datetime.now(ee.ZoneInfo("Asia/Tokyo")).strftime("%Y.%m")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (252, 253, 255))
    draw = ImageDraw.Draw(img)

    ee._draw_network_illustration(draw, accent)
    ee._draw_brand(draw, accent)
    ee._draw_tags(draw, category, date_label, accent)

    headline_font = ee._jp_font(validated["title_font_size"], bold=True)
    navy = (7, 30, 66)
    y = 160
    for line_text in validated["title_lines"]:
        bbox = draw.textbbox((0, 0), line_text, font=headline_font)
        draw.text((48, y - bbox[1]), line_text, font=headline_font, fill=navy)
        y += (bbox[3] - bbox[1]) + validated["title_line_gap"]

    sub_y = min(535, max(485, y + 18))
    draw.rectangle((48, sub_y + 2, 53, sub_y + 42), fill=accent)
    sub_font = ee._jp_font(validated["subheadline_font_size"], bold=True)
    sub_step = max(34, validated["subheadline_font_size"] + 11)
    for index, line_text in enumerate(validated["subheadline_lines"]):
        draw.text((72, sub_y + index * sub_step), line_text, font=sub_font, fill=(18, 42, 79))

    img.save(output_path, "PNG", optimize=True)
    return output_path


def _request_layout_plan(pipeline_module: Any, headline: str, subheadline: str) -> dict[str, Any] | None:
    if not ENABLE_EYECATCH_LAYOUT_OPTIMIZER:
        return None
    if bool(getattr(pipeline_module, "SYNTHETIC_REGRESSION_MODE", False)):
        return None
    try:
        response = pipeline_module._generate_via_chat(
            EYECATCH_LAYOUT_MODEL,
            _layout_prompt(headline, subheadline),
            config={
                "response_mime_type": "application/json",
                "response_json_schema": _LAYOUT_RESPONSE_SCHEMA,
                "max_output_tokens": EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS,
            },
            request_kind="eyecatch_layout",
            reserve=0,
            request_context="public_eyecatch_layout",
            count_as_deep_dive=False,
            request_origin="new",
        )
    except Exception as exc:
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.warning("[RUN178 EYECATCH LAYOUT FALLBACK] provider error: %s", exc)
        return None
    return _parse_plan_response(response)


def install(pipeline_module: Any) -> Any:
    """Patch only the public editorial renderer alias used by the production pipeline."""
    if getattr(pipeline_module, "_RUN178_EYECATCH_LAYOUT_OPTIMIZER_INSTALLED", False):
        return pipeline_module

    original = pipeline_module.generate_note_editorial_eyecatch

    def optimized_generate(
        title: str,
        summary: str,
        output_path: str,
        category: str | None = None,
        date_label: str | None = None,
    ) -> str:
        headline = ee.editorial_hook_from_title(title)
        subheadline = ee.editorial_subheadline(summary, headline)
        raw_plan = _request_layout_plan(pipeline_module, headline, subheadline)
        validated = validate_layout_plan(headline, subheadline, raw_plan)
        if validated is not None:
            try:
                return _render_with_validated_plan(
                    title,
                    summary,
                    output_path,
                    validated,
                    category=category,
                    date_label=date_label,
                )
            except Exception as exc:
                logger = getattr(pipeline_module, "logger", None)
                if logger is not None:
                    logger.warning("[RUN178 EYECATCH LAYOUT FALLBACK] render error: %s", exc)
        elif raw_plan is not None:
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning("[RUN178 EYECATCH LAYOUT FALLBACK] invalid typography plan")

        # No second model request: approved deterministic Run150/160 renderer is the safe fallback.
        return original(title, summary, output_path, category=category, date_label=date_label)

    pipeline_module.generate_note_editorial_eyecatch = optimized_generate
    pipeline_module._RUN178_EYECATCH_LAYOUT_OPTIMIZER_INSTALLED = True
    pipeline_module.RUN178_EYECATCH_LAYOUT_MODEL = EYECATCH_LAYOUT_MODEL
    return pipeline_module
