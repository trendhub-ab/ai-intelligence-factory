"""Run180: production semantic title direction for public note eyecatches.

The public eyecatch keeps the existing deterministic illustration, brand, tags and
subheadline renderer. Gemini 3.6 Flash is the primary title/typography director and
Gemini 3.5 Flash is the single provider fallback. Either model may compress the article
title into a shorter eyecatch title, choose semantic line breaks, bounded font sizes and
one exact emphasis phrase. Neither may introduce new facts, render pixels, or change the
visual motif.

If 3.6 is unavailable, the layout request falls back once to 3.5. If both provider sends
fail, or the returned plan fails the existing semantic/kinsoku/geometry guards, rendering
falls back to the already-approved deterministic path. This preserves zero image
generation while reserving 3.5 capacity for actual fallback use.
"""
from __future__ import annotations

import json
import re
from typing import Any

from PIL import Image, ImageDraw

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as r178


EYECATCH_LAYOUT_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash")
EYECATCH_LAYOUT_MODEL = EYECATCH_LAYOUT_MODELS[0]
EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS = 1400
TITLE_MIN_FONT = 52
TITLE_MAX_FONT = 76
SUB_MIN_FONT = 22
SUB_MAX_FONT = 28
TITLE_MAX_WIDTH = 760
SUB_MAX_WIDTH = 725
EYECATCH_TITLE_TARGET_MIN_CHARS = 15
EYECATCH_TITLE_TARGET_MAX_CHARS = 45
EYECATCH_TITLE_HARD_MAX_CHARS = 52
SOURCE_TITLE_MAX_CHARS = 96

_LAYOUT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        **r178._LAYOUT_RESPONSE_SCHEMA["properties"],
        "eyecatch_title": {"type": "string"},
        "highlight_text": {"type": "string"},
    },
    "required": [
        *r178._LAYOUT_RESPONSE_SCHEMA["required"],
        "eyecatch_title",
        "highlight_text",
    ],
}

_STOP_LATIN_TOKENS = {
    "a", "an", "and", "are", "at", "before", "by", "for", "from", "how", "in", "into", "is",
    "new", "now", "of", "on", "or", "the", "to", "with", "what", "why", "introducing",
}
_ELLIPSIS_RE = re.compile(r"(?:\.\.\.|…)")
_LATIN_HIGHLIGHT_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.+\-/]*")
_JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


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
    """Return the complete approved public title; never manufacture an ellipsis upstream."""
    clean = ee._clean_public_copy(title)
    clean = re.sub(r"^【[^】]{1,28}】\s*", "", clean).strip()
    if not clean:
        return "AIの変化を、わかりやすく。"
    return clean


def _layout_prompt(source_title: str, subheadline: str) -> str:
    payload = json.dumps(
        {"source_title": source_title, "subheadline": subheadline}, ensure_ascii=False
    )
    return f"""あなたは日本語テックメディアのエディトリアル・タイトル担当です。
1280x670のnoteアイキャッチ左側760pxで、スマートフォン縮小時にも一瞬で読めるタイトルを設計してください。

入力: {payload}

目的:
- 記事タイトルの事実と主題を維持したまま、アイキャッチ専用タイトルを短く、強く、読みやすくする。
- SEO用の記事タイトルとアイキャッチ用タイトルは同一でなくてよい。
- 説明を詰め込まず、「何の話か」と「なぜ気になるか」が一瞬で伝わる見出しにする。

絶対条件:
- eyecatch_titleはsource_titleの意味を圧縮するだけ。新しい事実、数値、性能、因果、評価、固有名詞を発明しない。
- 製品名、モデル名、バージョン番号など記事識別に必要な固有情報は維持する。
- eyecatch_titleは理想15〜45文字、最大52文字。元タイトルがすでに短く強ければ変更しなくてよい。
- source_titleに存在しない「...」「…」を追加して省略表示にしない。入り切らない場合は意味を保って短く言い換える。
- 「徹底解説」「完全ガイド」「まとめ」「最新情報」などSEOブログ的な煽り語を新規追加しない。
- 疑問形・断定形・変化提示のいずれも可。ただしsource_title以上に強い断定へ変えない。
- eyecatch_titleは画像だけを見ても自然な独立コピーとして意味が完結していること。「、」「，」「,」「：」「:」や接続途中の助詞・接続表現で終えない。元タイトルの前半を文字数で切り取っただけの断片は禁止。
- title_linesはeyecatch_titleを改行で分割したものだけ。文字の追加・削除・言い換えをtitle_lines側では行わない。
- headline相当のtitle_linesは1〜3行。2行を第一選択とし、2行では固有名詞・意味のまとまり・十分な文字サイズを守れない場合のみ3行を使う。必要な場合のみ3行とし、3行は正常なfallbackであり公開不可理由にしない。
- Noto Sans JP Blackを使う。headlineは52〜76px。760pxを超えない範囲でできるだけ大きくする。
- 固有名詞・英単語・複合語（例: OpenAI、Polars 2.0、エージェント、生成AI、モデル）を途中で切らない。
- subheadline_linesは入力subheadlineを1文字も変更せず、1〜2行へ分割するだけ。22〜28px。
- headline行間は8〜18px。
- 文節、句読点、助詞のまとまりを優先する。行頭に句読点・閉じ括弧・小書き仮名を置かない。行末に開き括弧を置かない。
- 短い1文字だけの行を作らない。
- 行長を機械的に均等化せず、意味のまとまりと視覚的重心を両立する。
- highlight_textにはeyecatch_title内で最も読者の目を止める「結論・問い・含意」の連続した1フレーズを完全一致で抜き出す。言い換えない。
- 製品名・モデル名だけ、英文の前置詞/接続詞で始まる断片、省略記号を含む断片はhighlight_textにしない。
- highlight_textは短すぎる単語だけ、製品名だけ、タイトル全体を避ける。原則として後半の意味ブロックを優先する。
- 画像、イラスト、背景、カテゴリ、日付、ロゴ、ビジュアル構造には一切触れない。
- JSON以外は返さない。
"""


def _required_source_tokens(source_title: str) -> set[str]:
    """Protect product/model/version identifiers without freezing ordinary English prose."""
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.+/\-]*|\d+(?:\.\d+)+", source_title)
    required: set[str] = set()

    def distinctive(token: str) -> bool:
        if re.fullmatch(r"\d+(?:\.\d+)+", token):
            return True
        if any(mark in token for mark in ("_", ".", "+", "/", "-")):
            return True
        if token.isupper() and len(token) >= 2:
            return True
        return any(ch.isupper() for ch in token[1:])

    for token in raw_tokens:
        lowered = token.casefold()
        if lowered in _STOP_LATIN_TOKENS:
            continue
        if distinctive(token):
            required.add(token)

    # Version numbers often anchor multi-word product/model names. Preserve nearby
    # title-cased words while allowing ordinary English sentence words to be compressed.
    for index, token in enumerate(raw_tokens):
        if not re.fullmatch(r"\d+(?:\.\d+)+", token):
            continue
        start = max(0, index - 1)
        end = min(len(raw_tokens), index + 5)
        for neighbour in raw_tokens[start:end]:
            lowered = neighbour.casefold()
            if lowered in _STOP_LATIN_TOKENS:
                continue
            if distinctive(neighbour) or re.fullmatch(r"[A-Z][a-z0-9]+", neighbour):
                required.add(neighbour)
    return required


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
    if _ELLIPSIS_RE.search(title) and not _ELLIPSIS_RE.search(source_title):
        return None
    # A visual headline must stand alone. Reject the exact failure mode where semantic
    # compression simply cuts the article title at a comma/colon or leaves a dangling
    # connective phrase such as "〜だが" / "〜では". Provider fallback can then try again.
    if re.search(r"[、，,:：]$", title):
        return None
    if re.search(
        r"(?:だが|ですが|しかし|けれど|けれども|ものの|一方で|ため|ので|のに|では|とは|なら|ながら|そして|また)$",
        title,
    ):
        return None

    # Compression may remove English connective words, but obvious model/product/version
    # identifiers from the source must survive. This catches the most damaging title rewrite
    # failure deterministically without pretending to semantically judge Japanese prose.
    folded_title = title.casefold()
    for token in _required_source_tokens(source_title):
        if token.casefold() not in folded_title:
            return None
    return title


_GENERAL_AVAILABILITY_RE = re.compile(
    r"^(?P<subject>.+?)\s+is\s+(?:now\s+)?generally\s+available[.!。]?$",
    re.IGNORECASE,
)


def _deterministic_safe_semantic_title(title: str) -> str:
    """Return a high-confidence short title only for exact general-availability wording."""
    clean = _source_title_for_direction(title)
    # Marketing-style lead-ins such as "Power your agents:" are not part of the product name.
    tail = re.split(r"[:：]", clean, maxsplit=1)[-1].strip()
    match = _GENERAL_AVAILABILITY_RE.fullmatch(tail)
    if match is None:
        return ""
    subject = match.group("subject").strip(" -–—,:：")
    if not subject:
        return ""
    candidate = f"{subject}、一般提供開始。"
    return candidate if _validate_eyecatch_title(clean, candidate) is not None else ""


def _validate_highlight_text(eyecatch_title: str, title_lines: list[str], value: Any) -> str:
    """Allow one exact semantic emphasis phrase; weak fragments silently stay navy."""
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
    if _ELLIPSIS_RE.search(highlight):
        return ""

    if not _JAPANESE_RE.search(highlight):
        tokens = _LATIN_HIGHLIGHT_TOKEN_RE.findall(highlight)
        lowered = [token.casefold() for token in tokens]
        if not tokens:
            return ""
        if lowered[0] in _STOP_LATIN_TOKENS or lowered[-1] in _STOP_LATIN_TOKENS:
            return ""
        if len(tokens) == 1:
            return ""
        looks_name_only = all(
            token.isupper() or (token[:1].isupper() and token[1:].isalnum())
            for token in tokens
        )
        if looks_name_only:
            return ""
        meaningful = [
            token for token in tokens
            if token.casefold() not in _STOP_LATIN_TOKENS and len(token) >= 4
        ]
        if not meaningful:
            return ""
    return highlight


def _validate_layout_plan(source_title: str, subheadline: str, plan: Any) -> dict[str, Any] | None:
    """Fail closed: title compression is bounded; line layout and geometry stay deterministic."""
    if not isinstance(plan, dict):
        return None

    eyecatch_title = _validate_eyecatch_title(source_title, plan.get("eyecatch_title"))
    if eyecatch_title is None:
        return None

    title_lines = r178._coerce_lines(plan.get("title_lines"), 3)
    sub_lines = r178._coerce_lines(plan.get("subheadline_lines"), 2)
    if title_lines is None or sub_lines is None:
        return None
    if r178._canonical_partition_text("".join(title_lines)) != r178._canonical_partition_text(eyecatch_title):
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
        "eyecatch_title": eyecatch_title,
        "title_lines": title_lines,
        "title_font_size": title_size,
        "title_line_gap": line_gap,
        "subheadline_lines": sub_lines,
        "subheadline_font_size": sub_size,
        "highlight_text": _validate_highlight_text(
            eyecatch_title, title_lines, plan.get("highlight_text")
        ),
    }



def _ascii_token_split(lines: list[str]) -> bool:
    """Return True when a line break cuts through one ASCII product/model token."""
    for left, right in zip(lines, lines[1:]):
        if not left or not right:
            continue
        if re.search(r"[A-Za-z0-9_.+\-/]$", left) and re.match(r"^[A-Za-z0-9_.+\-/]", right):
            return True
    return False


# Emergency floor only for complete-title preservation after semantic-plan validation fails.
COMPLETE_FALLBACK_TITLE_MIN_FONT = 44


def _fit_complete_title_lines(draw: ImageDraw.ImageDraw, clean: str) -> tuple[int, list[str]] | None:
    """Fit the complete bounded public title without rewriting, ellipsis, or ASCII token splits."""
    canonical = r178._canonical_partition_text(clean)
    if not canonical:
        return None

    length = len(clean)
    for size in range(50, COMPLETE_FALLBACK_TITLE_MIN_FONT - 1, -2):
        font = ee._jp_font(size, bold=True)
        best: tuple[float, list[str]] | None = None

        def consider(lines: list[str]) -> None:
            nonlocal best
            if not 1 <= len(lines) <= 3 or any(not line for line in lines):
                return
            if r178._canonical_partition_text("".join(lines)) != canonical:
                return
            if not r178._kinsoku_ok(lines) or _ascii_token_split(lines):
                return
            widths = [ee._text_width(draw, line, font) for line in lines]
            if any(width > TITLE_MAX_WIDTH for width in widths):
                return
            # Prefer visually balanced rows while mildly penalizing a very short final row.
            balance = max(widths) - min(widths)
            last_penalty = max(0.0, (sum(widths) / len(widths)) * 0.55 - widths[-1])
            score = balance + last_penalty
            if best is None or score < best[0]:
                best = (score, lines)

        consider([clean.strip()])
        for i in range(2, max(2, length - 1)):
            left = clean[:i].strip()
            right = clean[i:].strip()
            consider([left, right])
        for i in range(2, max(2, length - 3)):
            for j in range(i + 2, length - 1):
                first = clean[:i].strip()
                second = clean[i:j].strip()
                third = clean[j:].strip()
                consider([first, second, third])

        if best is not None:
            return size, best[1]
    return None


def _deterministic_semantic_fallback_plan(title: str, summary: str) -> dict[str, Any] | None:
    """Build a zero-provider plan for narrowly recognized, semantically lossless patterns."""
    candidate = _deterministic_safe_semantic_title(title)
    if not candidate:
        return None
    return _deterministic_complete_title_plan(candidate, summary)


def _deterministic_complete_title_plan(title: str, summary: str) -> dict[str, Any] | None:
    """Build a zero-provider fallback that never truncates a bounded eyecatch title.

    The historical renderer clips the public headline to 34 characters with an ellipsis.
    For any cleaned title that already fits the Run180 hard semantic budget, preserve every
    character and solve the problem only with line breaks/font fitting. Longer titles keep
    the legacy fallback until they receive a validated semantic compression.
    """
    clean = ee._clean_public_copy(title)
    clean = re.sub(r"^【[^】]{1,28}】\s*", "", clean).strip()
    canonical = r178._canonical_partition_text(clean)
    if not canonical or len(canonical) > EYECATCH_TITLE_HARD_MAX_CHARS:
        return None

    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    fitted = _fit_complete_title_lines(draw, clean)
    if fitted is None:
        return None
    title_size, title_lines = fitted
    subheadline = ee.editorial_subheadline(summary, clean)
    sub_size = 24
    sub_font = ee._jp_font(sub_size, bold=True)
    sub_lines = ee._wrap_chars(draw, subheadline, sub_font, SUB_MAX_WIDTH, 2)
    if not sub_lines:
        sub_lines = ["難しい変化を、仕事と暮らしの目線で読み解く。"]

    return {
        "eyecatch_title": clean,
        "title_lines": title_lines,
        "title_font_size": title_size,
        "title_line_gap": 10 if len(title_lines) >= 3 else 12,
        "subheadline_lines": sub_lines,
        "subheadline_font_size": sub_size,
        "highlight_text": "",
    }

def _request_layout_plan(
    pipeline_module: Any, source_title: str, subheadline: str
) -> dict[str, Any] | None:
    if bool(getattr(pipeline_module, "SYNTHETIC_REGRESSION_MODE", False)):
        return None

    prompt = _layout_prompt(source_title, subheadline)
    logger = getattr(pipeline_module, "logger", None)
    for model_name in EYECATCH_LAYOUT_MODELS:
        try:
            response = pipeline_module._generate_via_chat(
                model_name,
                prompt,
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
            return _parse_plan_response(response)
        except Exception as exc:
            if logger is not None:
                logger.warning(
                    "[RUN180 EYECATCH LAYOUT PROVIDER FALLBACK] model=%s error=%s",
                    model_name,
                    exc,
                )
    return None


def install(pipeline_module: Any) -> Any:
    """Replace the public renderer alias with validated 3.6 -> 3.5 title direction."""
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
        # Subheadline generation is intentionally unchanged. Run229 scope is title only.
        existing_headline = ee.editorial_hook_from_title(title, max_chars=48)
        subheadline = ee.editorial_subheadline(summary, existing_headline)
        raw_plan = _request_layout_plan(pipeline_module, source_title, subheadline)
        validated = _validate_layout_plan(source_title, subheadline, raw_plan)
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

        # After the bounded 3.6 -> 3.5 provider route, use a provider-free complete-title
        # plan for bounded titles before the historical renderer so fallback never
        # turns a valid 35-52 character headline into a visibly cut-off ellipsis.
        semantic_plan = _deterministic_semantic_fallback_plan(title, summary)
        if semantic_plan is not None:
            try:
                return r178._render_with_validated_plan(
                    title,
                    summary,
                    output_path,
                    semantic_plan,
                    category=category,
                    date_label=date_label,
                )
            except Exception as exc:
                logger = getattr(pipeline_module, "logger", None)
                if logger is not None:
                    logger.warning("[RUN180 EYECATCH SEMANTIC FALLBACK] render error: %s", exc)

        complete_plan = _deterministic_complete_title_plan(title, summary)
        if complete_plan is not None:
            try:
                return r178._render_with_validated_plan(
                    title,
                    summary,
                    output_path,
                    complete_plan,
                    category=category,
                    date_label=date_label,
                )
            except Exception as exc:
                logger = getattr(pipeline_module, "logger", None)
                if logger is not None:
                    logger.warning("[RUN180 EYECATCH COMPLETE FALLBACK] render error: %s", exc)

        # The legacy renderer truncates long public headlines with an ellipsis.
        # An invalid or unavailable semantic plan must never produce a cut-off
        # image that can be mistaken for a publication-ready eyecatch.
        clean_title = ee._clean_public_copy(title).strip()
        if len(r178._canonical_partition_text(clean_title)) > 34:
            raise ValueError("Cannot render a complete eyecatch title with the legacy fallback")
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
    pipeline_module.RUN180_EYECATCH_LAYOUT_MODELS = EYECATCH_LAYOUT_MODELS
    pipeline_module.RUN180_EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS = EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS
    pipeline_module.RUN180_EYECATCH_TITLE_MIN_FONT = TITLE_MIN_FONT
    pipeline_module.RUN180_EYECATCH_TITLE_TARGET_MAX_CHARS = EYECATCH_TITLE_TARGET_MAX_CHARS
    pipeline_module.RUN180_EYECATCH_TITLE_HARD_MAX_CHARS = EYECATCH_TITLE_HARD_MAX_CHARS
    return pipeline_module
