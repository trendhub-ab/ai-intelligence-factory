"""Run296: reader-approved note editorial format v2.

This zero-extra-provider policy layer applies the first real-draft visual review findings:
- the note intro heading becomes ``どんな内容？`` and the redundant ``何が出た？`` row is removed;
- the subscriber CTA uses the reader-approved plain Japanese copy;
- eyecatches omit the lower explanatory subheadline;
- long article titles may not be reused verbatim as eyecatch copy;
- selected Japanese compounds may not be split across title-line boundaries;
- the reviewed Netflix GenRec specimen uses the exact approved three-line copy and complete
  orange phrase ``舵を切った理由``.

The layer does not publish, mutate note, or add a model request. Future non-specimen eyecatches
continue to use Run180's existing single bounded layout call; this layer only tightens its prompt
and validation plus the deterministic renderer presentation.
"""
from __future__ import annotations

import re
from typing import Any

import editorial_eyecatch as ee
import run180_eyecatch_semantic_layout as r180
import run181_eyecatch_visual_balance as r181
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


def _remove_what_row(text: str) -> str:
    pattern = re.compile(
        r"(?ms)^\*\*何が出た？\*\*\s{2,}\n.*?(?=^\*\*(?:なぜ重要？|結論は？)\*\*|^###\s+元情報\s*$|^##\s+|\Z)"
    )
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
    return pipeline_module
