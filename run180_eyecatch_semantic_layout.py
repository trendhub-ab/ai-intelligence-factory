"""Run180: production semantic title direction for public note eyecatches.

The public eyecatch keeps the existing deterministic illustration, brand and tags.
Gemini 3.5 Flash is used exactly once as a title/typography director: it may compress
the article title into a shorter eyecatch title, choose semantic line breaks, bounded
font sizes and one exact emphasis phrase. It may not introduce new facts, render pixels,
change the visual motif, or trigger a second provider request.

Run230 removes the lower subheadline/lead from the public eyecatch entirely. The Gemini
layout request is therefore title-only as well: no subheadline text is generated, planned,
validated, or rendered. Provider, JSON, semantic-guard, kinsoku or geometry failure falls
back directly to the approved deterministic renderer, which follows the same no-subheadline
contract.
"""
from __future__ import annotations

import json
import re
from typing import Any

from PIL import Image, ImageDraw

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as r178


EYECATCH_LAYOUT_MODEL = "gemini-3.5-flash"
EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS = 1200
TITLE_MIN_FONT = 52
TITLE_MAX_FONT = 76
TITLE_MAX_WIDTH = 760
EYECATCH_TITLE_TARGET_MIN_CHARS = 15
EYECATCH_TITLE_TARGET_MAX_CHARS = 45
EYECATCH_TITLE_HARD_MAX_CHARS = 52
SOURCE_TITLE_MAX_CHARS = 96

_LAYOUT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "eyecatch_title": {"type": "string"},
        "title_lines": {"type": "array", "items": {"type": "string"}},
        "title_font_size": {"type": "integer"},
        "title_line_gap": {"type": "integer"},
        "highlight_text": {"type": "string"},
    },
    "required": [
        "eyecatch_title",
        "title_lines",
        "title_font_size",
        "title_line_gap",
        "highlight_text",
    ],
}

_STOP_LATIN_TOKENS = {
    "a", "an", "and", "are", "at", "by", "for", "from", "how", "in", "into", "is",
    "new", "now", "of", "on", "or", "the", "to", "with", "what", "why", "introducing",
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


def _source_title_for_direction(title: str) -> str:
    """Return clean public source copy without applying the old hook truncation."""
    clean = ee._clean_public_copy(title)
    clean = re.sub(r"^【[^】]{1,28}】\s*", "", clean).strip()
    if not clean:
        return "AIの変化を、わかりやすく。"
    if len(clean) <= SOURCE_TITLE_MAX_CHARS:
        return clean
    return clean[:SOURCE_TITLE_MAX_CHARS].rstrip("、。！？!? ") + "…"


def _layout_prompt(source_title: str) -> str:
    payload = json.dumps({"source_title": source_title}, ensure_ascii=False)
    return f"""あなたは日本語テックメディアのエディトリアル・タイトル担当です。
1280x670のnoteアイキャッチ左側760pxで、スマートフォン縮小時にも一瞬で読めるタイトルを設計してください。

入力: {payload}

目的:
- 記事タイトルの事実と主題を維持したまま、アイキャッチ専用タイトルを短く、強く、読みやすくする。
- SEO用の記事タイトルとアイキャッチ用タイトルは同一でなくてよい。
- 説明を詰め込まず、「何の話か」と「なぜ気になるか」が一瞬で伝わる見出しにする。
- アイキャッチ下部に説明文は置かない。タイトルだけで意味が通るようにする。

絶対条件:
- eyecatch_titleはsource_titleの意味を圧縮するだけ。新しい事実、数値、性能、因果、評価、固有名詞を発明しない。
- 製品名、モデル名、バージョン番号など記事識別に必要な固有情報は維持する。
- eyecatch_titleは理想15〜45文字、最大52文字。元タイトルがすでに短く強ければ変更しなくてよい。
- 「徹底解説」「完全ガイド」「まとめ」「最新情報」などSEOブログ的な煽り語を新規追加しない。
- 疑問形・断定形・変化提示のいずれも可。ただしsource_title以上に強い断定へ変えない。
- title_linesはeyecatch_titleを改行で分割したものだけ。文字の追加・削除・言い換えをtitle_lines側では行わない。
- title_linesは1〜3行。原則2〜3行を優先する。
- Noto Sans JP Blackを使う。headlineは52〜76px。760pxを超えない範囲でできるだけ大きくする。
- 固有名詞・英単語・複合語（例: OpenAI、Polars 2.0、エージェント、生成AI、モデル）を途中で切らない。
- headline行間は8〜18px。
- 文節、句読点、助詞のまとまりを優先する。行頭に句読点・閉じ括弧・小書き仮名を置かない。行末に開き括弧を置かない。
- 短い1文字だけの行を作らない。
- 行長を機械的に均等化せず、意味のまとまりと視覚的重心を両立する。
- highlight_textにはeyecatch_title内で最も読者の目を止める「結論・問い・含意」の連続した1フレーズを完全一致で抜き出す。言い換えない。
- highlight_textは短すぎる単語だけ、製品名だけ、タイトル全体を避ける。原則として後半の意味ブロックを優先する。
- 下部説明文、サブヘッド、リード文は生成しない。
- 画像、イラスト、背景、カテゴリ、日付、ロゴ、ビジュアル構造には一切触れない。
- JSON以外は返さない。
"""


def _required_source_tokens(source_title: str) -> set[str]:
    """Protect obvious Latin product/model/version identifiers during title compression."""
    tokens = set()
    for match in re.findall(r"[A-Za-z][A-Za-z0-9_.+\-/]*|\d+(?:\.\d+)+", source_title):
        lowered = match.lower()
        if lowered in _STOP_LATIN_TOKENS:
            continue
        if match.isalpha() and len(match) < 2:
            continue
        tokens.add(match)
    return tokens


def _validate_eyecatch_title(source_title: str, value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    title = re.sub(r"\s+", " ", value).strip()
    if not title or "\n" in value or "\r" in value:
        return None
    canonical = r178._canonical_partition_text(title)
    if not canonical or len(canonical) > EYECATCH_TITLE_HARD_MAX_CHARS:
        return None
    if re.search(r"https?://|[#*_`>]", title):
        return None

    folded_title = title.casefold()
    for token in _required_source_tokens(source_title):
        if token.casefold() not in folded_title:
            return None
    return title


def _validate_highlight_text(eyecatch_title: str, title_lines: list[str], value: Any) -> str:
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
    if canonical not in r178._canonical_partition_text(eyecatch_title):
        return ""
    if len(canonical) / len(total) > 0.70:
        return ""
    return highlight


def _validate_layout_plan(source_title: str, plan: Any) -> dict[str, Any] | None:
    """Fail closed: title compression is bounded; line layout and geometry stay deterministic."""
    if not isinstance(plan, dict):
        return None

    eyecatch_title = _validate_eyecatch_title(source_title, plan.get("eyecatch_title"))
    if eyecatch_title is None:
        return None

    title_lines = r178._coerce_lines(plan.get("title_lines"), 3)
    if title_lines is None:
        return None
    if r178._canonical_partition_text("".join(title_lines)) != r178._canonical_partition_text(eyecatch_title):
        return None
    if not r178._kinsoku_ok(title_lines):
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
    if title_fit is None:
        return None

    title_size, _ = title_fit
    return {
        "eyecatch_title": eyecatch_title,
        "title_lines": title_lines,
        "title_font_size": title_size,
        "title_line_gap": line_gap,
        "highlight_text": _validate_highlight_text(
            eyecatch_title, title_lines, plan.get("highlight_text")
        ),
    }


def _request_layout_plan(pipeline_module: Any, source_title: str) -> dict[str, Any] | None:
    if bool(getattr(pipeline_module, "SYNTHETIC_REGRESSION_MODE", False)):
        return None
    try:
        response = pipeline_module._generate_via_chat(
            EYECATCH_LAYOUT_MODEL,
            _layout_prompt(source_title),
            config={
                "response_mime_type": "application/json",
                "response_json_schema": _LAYOUT_RESPONSE_SCHEMA,
                "max_output_tokens": EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS,
                "thinking_config": {"thinking_level": "minimal"},
            },
            request_kind="eyecatch_layout",
            reserve=0,
            request_context="public_eyecatch_semantic_title_layout",
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
    """Replace the public renderer alias with the validated one-call title direction path."""
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
        source_title = _source_title_for_direction(title)
        raw_plan = _request_layout_plan(pipeline_module, source_title)
        validated = _validate_layout_plan(source_title, raw_plan)
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
                logger.warning("[RUN180 EYECATCH LAYOUT FALLBACK] invalid semantic title plan")

        # Safety invariant: no second model request. The deterministic fallback keeps the
        # same brand/background/visual motif and the Run230 no-subheadline contract.
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
    pipeline_module.RUN180_EYECATCH_TITLE_TARGET_MAX_CHARS = EYECATCH_TITLE_TARGET_MAX_CHARS
    pipeline_module.RUN180_EYECATCH_TITLE_HARD_MAX_CHARS = EYECATCH_TITLE_HARD_MAX_CHARS
    return pipeline_module
