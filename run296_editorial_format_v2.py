"""Run296: reader-approved note editorial format v2.

This zero-extra-provider policy layer applies the first real-draft visual review findings:
- the note intro heading becomes ``どんな内容？`` and the redundant ``何が出た？`` label is removed while its summary text is preserved;
- the subscriber CTA uses the reader-approved plain Japanese copy;
- eyecatches omit the lower explanatory subheadline;
- long article titles may not be reused verbatim as eyecatch copy;
- selected Japanese compounds may not be split across title-line boundaries;
- the reviewed Netflix GenRec specimen uses the exact approved three-line copy and complete
  orange phrase ``舵を切った理由``.

Run306 further refines the same deterministic eyecatch renderer without adding a provider call:
- headline size is derived from measured text geometry instead of the model-suggested size;
- the reviewed Netflix specimen scale is the normal-title maximum;
- two-line and three-line title blocks share one visual center instead of fixed top anchors.

The layer does not publish, mutate note, or add a model request. Future non-specimen eyecatches
continue to use Run180's existing single bounded layout call; this layer only tightens its prompt
and validation plus the deterministic renderer presentation.

Image-rendering modules are imported lazily inside the production installer so the pure text and
policy helpers remain testable in the zero-Pillow required repository guard.
"""
from __future__ import annotations

import re
from typing import Any

import run222_note_presentation_integrity as r222

INTRO_HEADING_OLD = "30秒でわかるこの記事"
INTRO_HEADING_NEW = "どんな内容？"
REMOVE_SUMMARY_LABEL = "何が出た？"
CTA_HEADING = "有料サブスクのご案内"
CTA_BODY = (
    "有料サブスクでは、意思決定DBと月次ダイジェストを公開しています。"
    "AI情報の変化を追い、採用・様子見・見送りの判断を助けます。"
)
CTA_LINK_LABEL = "詳しくはこちら"

_LEGACY_CTA_HEADINGS = {
    "「自分はどうする？」まで判断したい方へ",
    "調査と判断の時間を減らしたい方へ",
    CTA_HEADING,
}

GENREC_SOURCE_TITLE = "Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。"
GENREC_EYECATCH_TITLE = "Netflix推薦の舞台裏LLMネイティブへ舵を切った理由"
GENREC_EYECATCH_LINES = (
    "Netflix推薦の舞台裏",
    "LLMネイティブへ",
    "舵を切った理由",
)
GENREC_HIGHLIGHT = "舵を切った理由"

# Run306 visual reference: the human-reviewed Netflix eyecatch renders its normal title at 72px
# and the existing Run183 20% conclusion emphasis at approximately 86px. Shorter copy may use
# this full scale; longer copy shrinks from this ceiling according to measured glyph geometry.
RUN306_TITLE_MAX_FONT = 72
RUN306_HIGHLIGHT_MAX_FONT = 86
RUN306_TITLE_MIN_FONT = 48
RUN306_VISUAL_CENTER_Y = 370

# These are high-confidence lexical units where an arbitrary character-width break is visibly
# worse than falling back to another plan. The list stays deliberately small and conservative.
PROTECTED_COMPOUNDS = (
    "舞台裏",
    "生成AI",
    "機械学習",
    "深層学習",
    "大規模言語モデル",
    "意思決定",
)


def _canon(value: str) -> str:
    return re.sub(r"[\s。．.!！?？、，,：:]", "", str(value or "")).casefold()


def is_genrec_title(value: str) -> bool:
    return _canon(value) == _canon(GENREC_SOURCE_TITLE)


def _line_boundaries(lines: list[str] | tuple[str, ...]) -> set[int]:
    boundaries: set[int] = set()
    offset = 0
    for line in list(lines)[:-1]:
        offset += len(str(line))
        boundaries.add(offset)
    return boundaries


def compounds_are_atomic(lines: list[str] | tuple[str, ...]) -> bool:
    joined = "".join(str(line) for line in lines)
    boundaries = _line_boundaries(lines)
    for compound in PROTECTED_COMPOUNDS:
        start = 0
        while True:
            index = joined.find(compound, start)
            if index < 0:
                break
            if any(index < boundary < index + len(compound) for boundary in boundaries):
                return False
            start = index + 1
    return True


def eyecatch_copy_is_distinct(source_title: str, eyecatch_title: str) -> bool:
    """Long SEO/article titles must be compressed for the visual surface.

    Very short titles (24 canonical characters or fewer) are allowed to remain unchanged because
    forced paraphrasing would add risk without improving scanability.
    """
    source = _canon(source_title)
    eyecatch = _canon(eyecatch_title)
    if not source or not eyecatch:
        return False
    return len(source) <= 24 or source != eyecatch


def adaptive_title_top(
    block_height: int,
    min_top: int,
    safe_bottom: int,
    *,
    visual_center_y: int = RUN306_VISUAL_CENTER_Y,
) -> int:
    """Center a measured title block while respecting the historical safe region.

    The old renderer fixed the three-line top at 226px (even above the two-line 234px anchor),
    which made dense copy look top-heavy. Run306 keeps those values only as minimum safe tops and
    places the measured block around one shared visual axis.
    """
    block = max(0, int(block_height))
    lower = int(min_top)
    upper = max(lower, int(safe_bottom) - block)
    preferred = int(round(int(visual_center_y) - block / 2.0))
    return max(lower, min(preferred, upper))


def _install_run306_adaptive_typography(r181_module: Any) -> None:
    """Patch Run181 geometry in-place after Run183, using zero additional model requests."""
    if getattr(r181_module, "_RUN306_ADAPTIVE_TYPOGRAPHY_INSTALLED", False):
        return

    # Keep Pillow on the lazy production path, matching the existing Run296 import contract.
    from PIL import Image, ImageDraw

    import editorial_eyecatch as ee

    original_profile = r181_module._impact_layout_profile

    # The attached/reviewed Netflix specimen is the ceiling, not a minimum. The orange conclusion
    # remains at the already-approved Run183 20% emphasis scale, capped at its current visual size.
    r181_module.IMPACT_TITLE_MAX_FONT = RUN306_TITLE_MAX_FONT
    r181_module.IMPACT_THREE_LINE_TITLE_MAX_FONT = RUN306_TITLE_MAX_FONT
    r181_module.IMPACT_HIGHLIGHT_MAX_FONT = RUN306_HIGHLIGHT_MAX_FONT

    def adaptive_title_size(lines: list[str], base_size: int, line_gap: int) -> int:
        """Choose the largest safe font from the reference ceiling downward.

        ``base_size`` remains in the signature for compatibility, but no longer controls the
        headline scale. The rendered text itself is the authority: short copy reaches the reviewed
        ceiling and long copy shrinks only as much as width/height require.
        """
        profile = original_profile(lines, line_gap)
        target = min(RUN306_TITLE_MAX_FONT, int(profile["title_max_font"]))
        effective_gap = int(profile["line_gap"])
        available_height = max(
            0,
            int(profile["title_safe_bottom"]) - int(profile["title_top"]),
        )
        probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
        draw = ImageDraw.Draw(probe)
        clean_lines = [str(line) for line in lines if str(line).strip()]
        if not clean_lines:
            return RUN306_TITLE_MIN_FONT
        for candidate in range(target, RUN306_TITLE_MIN_FONT - 1, -1):
            font = ee._jp_font(candidate, bold=True)
            widths = [ee._text_width(draw, line, font) for line in clean_lines]
            heights = [r181_module._run_bbox_height(draw, line, font) for line in clean_lines]
            block_height = sum(heights) + max(0, len(clean_lines) - 1) * effective_gap
            if all(width <= r181_module.TITLE_MAX_WIDTH for width in widths) and block_height <= available_height:
                return candidate
        # Run180 validation normally guarantees a fit. If an old validated plan still cannot fit,
        # use the smallest permitted size rather than enlarging it from a stale model hint.
        return RUN306_TITLE_MIN_FONT

    def adaptive_profile(lines: list[str], requested_gap: int) -> dict[str, int | bool]:
        profile = dict(original_profile(lines, requested_gap))
        effective_gap = int(profile["line_gap"])
        size = adaptive_title_size(lines, RUN306_TITLE_MAX_FONT, effective_gap)
        probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
        draw = ImageDraw.Draw(probe)
        font = ee._jp_font(size, bold=True)
        clean_lines = [str(line) for line in lines if str(line).strip()]
        heights = [r181_module._run_bbox_height(draw, line, font) for line in clean_lines]
        block_height = sum(heights) + max(0, len(clean_lines) - 1) * effective_gap
        profile["title_top"] = adaptive_title_top(
            block_height,
            int(profile["title_top"]),
            int(profile["title_safe_bottom"]),
        )
        return profile

    r181_module._impact_title_size = adaptive_title_size
    r181_module._impact_layout_profile = adaptive_profile
    r181_module._RUN306_ADAPTIVE_TYPOGRAPHY_INSTALLED = True
    r181_module.RUN306_TITLE_MAX_FONT = RUN306_TITLE_MAX_FONT
    r181_module.RUN306_HIGHLIGHT_MAX_FONT = RUN306_HIGHLIGHT_MAX_FONT
    r181_module.RUN306_VISUAL_CENTER_Y = RUN306_VISUAL_CENTER_Y


def _remove_what_row(text: str) -> str:
    """Remove only the redundant label line and preserve the summary body below it."""
    pattern = re.compile(r"(?m)^\*\*何が出た？\*\*[ \t]*(?:\n|$)")
    return pattern.sub("", text, count=1)


def _normalize_cta(text: str) -> str:
    heading_alt = "|".join(re.escape(item) for item in sorted(_LEGACY_CTA_HEADINGS, key=len, reverse=True))
    heading = re.search(rf"(?m)^###\s+(?:{heading_alt})\s*$", text)
    if heading is None:
        return text

    tail = text[heading.end():]
    link = re.search(r"\[[^\]]+\]\((https?://[^)]+)\)", tail)
    if link is None:
        # A malformed CTA should remain untouched and fail other publication checks rather than
        # losing its destination silently.
        return text
    url = link.group(1)
    new_block = f"### {CTA_HEADING}\n\n{CTA_BODY}\n\n[{CTA_LINK_LABEL}]({url})"
    # Run222 guarantees the subscriber CTA is the final action block in canonical manuscripts.
    return text[:heading.start()].rstrip() + "\n" + new_block


def normalize_article_format_v2(markdown_text: str) -> str:
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(
        rf"(?m)^##\s+{re.escape(INTRO_HEADING_OLD)}\s*$",
        f"## {INTRO_HEADING_NEW}",
        text,
        count=1,
    )
    text = _remove_what_row(text)
    text = _normalize_cta(text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def genrec_validated_plan() -> dict[str, Any]:
    return {
        "eyecatch_title": GENREC_EYECATCH_TITLE,
        "title_lines": list(GENREC_EYECATCH_LINES),
        "title_font_size": 64,
        "title_line_gap": 10,
        # Run296 intentionally draws no lower explanatory copy. These compatibility fields remain
        # so the plan shape is self-describing and safe for downstream historical helpers.
        "subheadline_lines": [],
        "subheadline_font_size": 22,
        "highlight_text": GENREC_HIGHLIGHT,
    }


def _install_eyecatch_policy(pipeline_module: Any) -> None:
    # Keep Pillow-dependent renderer modules off the pure import path used by required guards.
    import run180_eyecatch_semantic_layout as r180
    import run181_eyecatch_visual_balance as r181

    # Run306 is a deterministic refinement of the already-approved renderer. It is installed here
    # because Run296 is already the final production eyecatch presentation layer after Run183.
    _install_run306_adaptive_typography(r181)

    # Tighten the existing single-call Run180 direction prompt; do not add another request.
    original_prompt = r180._layout_prompt

    def editorial_v2_prompt(source_title: str, subheadline: str) -> str:
        return original_prompt(source_title, subheadline) + """

Run296追加条件:
- 24文字を超えるsource_titleをeyecatch_titleへそのまま複製しない。必ず意味を保って短くする。
- 日本語の複合語を文字幅都合で割らない。特に「舞台裏」のように一語として読む語は同じ行に置く。
- highlight_textは述語や結論の意味単位を欠かさない完全なフレーズにする。たとえば「舵を切った理由」を「切った理由」だけに縮めない。
- 下部説明文はRun296で廃止したため、subheadlineの見栄えを優先してタイトルを弱めない。
"""

    r180._layout_prompt = editorial_v2_prompt

    original_validate = r180._validate_layout_plan

    def editorial_v2_validate(source_title: str, subheadline: str, plan: Any) -> dict[str, Any] | None:
        validated = original_validate(source_title, subheadline, plan)
        if validated is None:
            return None
        if not eyecatch_copy_is_distinct(source_title, str(validated.get("eyecatch_title") or "")):
            return None
        lines = validated.get("title_lines") or []
        if not compounds_are_atomic(lines):
            return None
        # Deterministically repair the exact incomplete phrase observed in the first real draft.
        joined = "".join(str(line) for line in lines)
        if GENREC_HIGHLIGHT in joined and validated.get("highlight_text") == "切った理由":
            validated = dict(validated)
            validated["highlight_text"] = GENREC_HIGHLIGHT
        return validated

    r180._validate_layout_plan = editorial_v2_validate

    # Remove the bottom explanation globally. The badge/hook/title/footer remain intact.
    def no_subheadline(_draw: Any, _title: str, _summary: str, _validated: dict[str, Any]) -> tuple[list[str], int]:
        return [], 22

    r181._subheadline_lines = no_subheadline

    original_generate = pipeline_module.generate_note_editorial_eyecatch

    def editorial_v2_generate(
        title: str,
        summary: str,
        output_path: str,
        category: str | None = None,
        date_label: str | None = None,
    ) -> str:
        # The first production specimen was visually reviewed by the human publisher. Reproduce
        # that approved correction deterministically rather than asking the model to guess it.
        if is_genrec_title(title):
            return r181._render_balanced_plan(
                title,
                summary,
                output_path,
                genrec_validated_plan(),
                category=category,
                date_label=date_label,
                highlight_text=GENREC_HIGHLIGHT,
            )
        return original_generate(title, summary, output_path, category=category, date_label=date_label)

    pipeline_module.generate_note_editorial_eyecatch = editorial_v2_generate


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, "_RUN296_EDITORIAL_FORMAT_V2_INSTALLED", False):
        return pipeline_module

    # Make the new CTA recognizable to Run222's note-editor presentation transform as well.
    r222.CTA_HEADINGS.add(CTA_HEADING)

    original_build = pipeline_module.build_clean_note_manuscript

    def build_clean_note_manuscript(*args: Any, **kwargs: Any) -> str:
        return normalize_article_format_v2(original_build(*args, **kwargs))

    pipeline_module.build_clean_note_manuscript = build_clean_note_manuscript
    _install_eyecatch_policy(pipeline_module)

    pipeline_module._RUN296_EDITORIAL_FORMAT_V2_INSTALLED = True
    pipeline_module.RUN296_INTRO_HEADING = INTRO_HEADING_NEW
    pipeline_module.RUN296_CTA_HEADING = CTA_HEADING
    pipeline_module.RUN296_EYECATCH_BOTTOM_DESCRIPTION = False
    pipeline_module.RUN306_EYECATCH_ADAPTIVE_TYPOGRAPHY = True
    pipeline_module.RUN306_EYECATCH_TITLE_MAX_FONT = RUN306_TITLE_MAX_FONT
    pipeline_module.RUN306_EYECATCH_VISUAL_CENTER_Y = RUN306_VISUAL_CENTER_Y
    return pipeline_module
