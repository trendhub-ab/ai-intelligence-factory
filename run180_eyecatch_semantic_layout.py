"""Run180: production semantic typography for public note eyecatches.

Run178 proved the architecture but real visual QA exposed three production issues:
1. schema responses can live in ``response.parsed`` rather than ``response.text``;
2. Gemini 3.5 Flash's default thinking can consume a small 700-token budget before
   the tiny JSON layout body is emitted;
3. pre-truncating headlines at 34 characters can destroy meaning before the layout
   director sees the title.

This layer keeps the safety contract intact: exactly one layout-only Gemini request,
no model retry/fallback, no copy rewrite, strict kinsoku/geometry validation, and a
deterministic PIL fallback. Gemini chooses typography and one exact conclusion phrase;
code remains the final gate.
"""
from __future__ import annotations

import json
import re
from typing import Any

from PIL import Image, ImageDraw

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as r178


EYECATCH_LAYOUT_MODEL = "gemini-3.5-flash"
EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS = 1400
TITLE_MIN_FONT = 42
TITLE_MAX_FONT = 76
SUB_MIN_FONT = 22
SUB_MAX_FONT = 28
TITLE_MAX_WIDTH = 760
SUB_MAX_WIDTH = 725

_LAYOUT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        **r178._LAYOUT_RESPONSE_SCHEMA["properties"],
        "highlight_text": {"type": "string"},
    },
    "required": [*r178._LAYOUT_RESPONSE_SCHEMA["required"], "highlight_text"],
}


def _parse_plan_response(response: Any) -> dict[str, Any] | None:
    """Prefer google-genai's schema-aware parsed surface, then text compatibility."""
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    model_dump = getattr(parsed, "model_dump", None)
    if callable(model_dump):
        try:
            value = model_dump()
        except Exception:
            value = None
        if isinstance(value, dict):
            return value

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


def _layout_prompt(headline: str, subheadline: str) -> str:
    payload = json.dumps({"headline": headline, "subheadline": subheadline}, ensure_ascii=False)
    return f"""あなたは日本語エディトリアルデザインのタイポグラフィ担当です。
1280x670のnoteアイキャッチ左側760pxの文字領域を、スマートフォンの縮小表示でも一瞬で読めるように組んでください。

入力: {payload}

絶対条件:
- 文言は1文字も追加・削除・補完・言い換えしない。入力文字列を改行で分割するだけ。
- headlineは1〜3行。25文字以上の長いheadlineは原則3行を検討する。
- Noto Sans JP Blackを使う。headlineは42〜76px。48pxでは全角約15文字、42pxでは全角約17文字を1行の安全な目安とする。
- 760pxを超えそうな長い行を作らず、固有名詞・英単語・複合語（例: OpenAI、エージェント、生成AI、モデル）を途中で切らない。
- subheadlineは1〜2行、22〜28px。1行あたり全角約27文字以内を目安にする。
- headline行間は8〜18px。
- 文節、句読点、助詞のまとまりを優先する。行頭に句読点・閉じ括弧・小書き仮名を置かない。行末に開き括弧を置かない。
- 短い1文字だけの行を作らない。
- 行長を機械的に均等化するのではなく、意味のまとまりと視覚的な重心を両立する。
- highlight_textにはheadline内で最も読者の目を止める「結論・問い・含意」の連続した1フレーズを、headlineから完全一致で抜き出す。言い換えない。
- highlight_textは原則として後半の意味ブロックを選び、短すぎる単語だけやタイトル全体は選ばない。複数行にまたがってもよい。
- 例: 「AIは重要。でも正直、もう追いきれない。」なら「もう追いきれない。」。
- 例: 「生成AIの『速さ』競争が変わる。小さなモデルは実務でどこまで使えるのか。」なら「小さなモデルは実務でどこまで使えるのか。」。
- JSON以外は返さない。
"""


def _validate_highlight_text(headline: str, title_lines: list[str], value: Any) -> str:
    """Allow one exact, restrained contiguous emphasis phrase; otherwise disable color only."""
    if not isinstance(value, str):
        return ""
    highlight = value.strip()
    joined = "".join(title_lines)
    canonical = r178._canonical_partition_text(highlight)
    total = r178._canonical_partition_text(joined)
    if len(canonical) < 4 or not total:
        return ""
    if highlight not in joined or joined.count(highlight) != 1:
        return ""
    if canonical not in r178._canonical_partition_text(headline):
        return ""
    # Keep orange as a focal accent rather than turning most of the title orange.
    if len(canonical) / len(total) > 0.70:
        return ""
    return highlight


def _validate_layout_plan(headline: str, subheadline: str, plan: Any) -> dict[str, Any] | None:
    """Fail closed: Gemini may partition text, never rewrite it or exceed geometry."""
    if not isinstance(plan, dict):
        return None

    title_lines = r178._coerce_lines(plan.get("title_lines"), 3)
    sub_lines = r178._coerce_lines(plan.get("subheadline_lines"), 2)
    if title_lines is None or sub_lines is None:
        return None
    if r178._canonical_partition_text("".join(title_lines)) != r178._canonical_partition_text(headline):
        return None
    if r178._canonical_partition_text("".join(sub_lines)) != r178._canonical_partition_text(subheadline):
        return None
    if not r178._kinsoku_ok(title_lines) or not r178._kinsoku_ok(sub_lines):
        return None

    try:
        line_gap = int(plan.get("title_line_gap"))
    except (TypeError, ValueError):
        return None
    line_gap = max(8, min(18, line_gap))

    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    title_fit = r178._fit_requested_lines(
        draw,
        title_lines,
        plan.get("title_font_size"),
        TITLE_MIN_FONT,
        TITLE_MAX_FONT,
        TITLE_MAX_WIDTH,
    )
    sub_fit = r178._fit_requested_lines(
        draw,
        sub_lines,
        plan.get("subheadline_font_size"),
        SUB_MIN_FONT,
        SUB_MAX_FONT,
        SUB_MAX_WIDTH,
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
        "highlight_text": _validate_highlight_text(headline, title_lines, plan.get("highlight_text")),
    }


def _request_layout_plan(pipeline_module: Any, headline: str, subheadline: str) -> dict[str, Any] | None:
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
                "thinking_config": {"thinking_level": "minimal"},
            },
            request_kind="eyecatch_layout",
            reserve=0,
            request_context="public_eyecatch_semantic_layout",
            count_as_deep_dive=False,
            request_origin="new",
        )
    except Exception as exc:
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.warning("[RUN180 EYECATCH LAYOUT FALLBACK] provider error: %s", exc)
        return None
    return _parse_plan_response(response)


def install(pipeline_module: Any) -> Any:
    """Replace the public renderer alias with the validated one-call Run180 path."""
    if getattr(pipeline_module, "_RUN180_EYECATCH_SEMANTIC_LAYOUT_INSTALLED", False):
        return pipeline_module

    deterministic_fallback = ee.generate_note_editorial_eyecatch

    def semantic_generate(
        title: str,
        summary: str,
        output_path: str,
        category: str | None = None,
        date_label: str | None = None,
    ) -> str:
        # Keep the complete public title for normal note-length headlines. This
        # avoids hallucinated completion of a pre-truncated ellipsis while still
        # bounding pathological input before the layout request.
        headline = ee.editorial_hook_from_title(title, max_chars=48)
        subheadline = ee.editorial_subheadline(summary, headline)
        raw_plan = _request_layout_plan(pipeline_module, headline, subheadline)
        validated = _validate_layout_plan(headline, subheadline, raw_plan)
        if validated is not None:
            try:
                return r178._render_with_validated_plan(
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
                    logger.warning("[RUN180 EYECATCH LAYOUT FALLBACK] render error: %s", exc)
        elif raw_plan is not None:
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning("[RUN180 EYECATCH LAYOUT FALLBACK] invalid semantic typography plan")

        # Crucial safety invariant: never call Run178's wrapped renderer here,
        # because that could spend a second Gemini request. Fallback is purely
        # deterministic and still inherits Run179's Noto/Inter font policy.
        return deterministic_fallback(
            title,
            summary,
            output_path,
            category=category,
            date_label=date_label,
        )

    pipeline_module.generate_note_editorial_eyecatch = semantic_generate
    pipeline_module._RUN180_EYECATCH_SEMANTIC_LAYOUT_INSTALLED = True
    pipeline_module.RUN180_EYECATCH_LAYOUT_MODEL = EYECATCH_LAYOUT_MODEL
    pipeline_module.RUN180_EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS = EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS
    pipeline_module.RUN180_EYECATCH_TITLE_MIN_FONT = TITLE_MIN_FONT
    return pipeline_module
