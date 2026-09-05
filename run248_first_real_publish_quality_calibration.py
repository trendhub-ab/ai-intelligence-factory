"""Run248: First Real Publish quality calibration.

The first end-to-end real note draft proved that the automation path works, while also
exposing a gap between internal diagnostics and what is acceptable to publish.  This
zero-provider-call layer fixes only deterministic publication defects and calibration:

* preserve the already-approved eyecatch background/illustration exactly as-is;
* if the semantic eyecatch director falls back or loses emphasis, re-render the same
  background with current orange emphasis, larger typography and the lower title block;
* never split short Latin/model tokens such as ``LLM`` across fallback title lines;
* make supplemental Evidence URLs real Markdown links before note HTML conversion;
* use the product name ``月次ダイジェスト`` consistently and strengthen the CTA value line;
* turn multi-axis Reader Experience weakness into an editorial-review disposition instead
  of allowing a nominal Ready merely because no single hard fact gate failed;
* catch the exact high-confidence Japanese corruption classes observed in the first real
  publish specimen without adding a model call or broad dictionary guessing.

No public release action is added.  No Gemini/model call site is added.  Fact/Evidence/
Decision constraints are never relaxed.
"""
from __future__ import annotations

import itertools
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as r178
import run180_eyecatch_semantic_layout as r180
import run181_eyecatch_visual_balance as r181


_INSTALLED_ATTR = "_run248_first_real_publish_quality_calibration_installed"
PROMPT_MARKER = "RUN248_FIRST_REAL_PUBLISH_QUALITY"
READER_VALUE_MARKER = "reader_value_review:"

# Keep the previously approved art direction.  Run182/183 already established this orange.
HIGHLIGHT_ORANGE = (242, 140, 40)  # #F28C28
TITLE_MAX_WIDTH = 760
TITLE_MIN_FONT = 54
TITLE_MAX_FONT = 76
TITLE_LINE_GAP = 12

_CORE_READER_KEYS = (
    "accessibility",
    "curiosity_pull",
    "reader_enjoyment",
    "narrative_pull",
    "jargon_translation",
    "non_engineer_core_clarity",
    "information_budget",
    "reader_temperature_rhythm",
)

# Narrow, high-confidence additions to Run227, derived from the actual first-real-publish
# manuscript.  They deliberately avoid broad Japanese grammar guessing.
_SURFACE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"をに(?=(?:速|遅|高|低|大|小|強|弱|増|減|変|近|遠|広|狭|長|短|重|軽))"),
        "particle_collision_wo_ni",
    ),
    (re.compile(r"主主要"), "duplicated_primary_modifier"),
    (re.compile(r"眼砲"), "malformed_lexeme_ganpou"),
)


def _canonical(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _protected_spans(text: str) -> list[tuple[int, int]]:
    """Protect compact quoted/model phrases from deterministic fallback line breaks."""
    spans: list[tuple[int, int]] = []
    for pattern in (r"「[^」\n]{1,18}」", r"『[^』\n]{1,18}』", r"\([^()\n]{1,18}\)"):
        for match in re.finditer(pattern, text):
            spans.append((match.start(), match.end()))
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9_.+\-/]*", text):
        spans.append((match.start(), match.end()))
    return spans


def _allowed_break_indices(text: str) -> list[int]:
    spans = _protected_spans(text)
    allowed: list[int] = []
    for index in range(2, len(text) - 1):
        prev_char, next_char = text[index - 1], text[index]
        if prev_char in r178._FORBIDDEN_LINE_END or next_char in r178._FORBIDDEN_LINE_START:
            continue
        if any(start < index < end for start, end in spans):
            continue
        allowed.append(index)
    return allowed


def _boundary_penalty(line: str) -> int:
    if not line:
        return 100
    # Punctuation/particles are natural places to end a Japanese display line.
    return 0 if line[-1] in "、。！？!?：:がはをにでとへも" else 3


def _best_title_layout(headline: str) -> tuple[list[str], int]:
    """Choose the largest 2/3-line fallback layout before preferring fewer lines.

    The old deterministic fallback forced a two-line split first and shrank all the way
    toward 50px.  That is exactly how the first real draft became too small and split
    ``LLM`` as ``L`` / ``LM``.  Here font size is the primary objective, then balance.
    """
    value = str(headline or "").strip()
    if not value:
        return ["AIの変化を、わかりやすく。"], 64

    probe = Image.new("RGB", (ee.WIDTH, ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    breaks = _allowed_break_indices(value)
    candidates: list[tuple[tuple[float, ...], list[str], int]] = []

    for line_count in (2, 3):
        if len(breaks) < line_count - 1:
            continue
        for combo in itertools.combinations(breaks, line_count - 1):
            points = (0, *combo, len(value))
            lines = [value[points[i]:points[i + 1]].strip() for i in range(line_count)]
            if any(not line for line in lines) or not r178._kinsoku_ok(lines):
                continue
            for size in range(TITLE_MAX_FONT, TITLE_MIN_FONT - 1, -2):
                font = ee._jp_font(size, bold=True)
                widths = [ee._text_width(draw, line, font) for line in lines]
                if any(width > TITLE_MAX_WIDTH for width in widths):
                    continue
                balance = max(widths) - min(widths)
                boundary = sum(_boundary_penalty(line) for line in lines[:-1])
                # Largest text wins. For equal size, prefer fewer lines, then balance/natural breaks.
                score = (-float(size), float(line_count), float(boundary), float(balance))
                candidates.append((score, lines, size))
                break

    if candidates:
        _score, lines, size = min(candidates, key=lambda item: item[0])
        return lines, size

    # Last-resort existing fitter. This path remains deterministic and preserves no-token-split
    # protections whenever a candidate layout exists.
    font, lines = ee._fit_headline(draw, value, max_width=TITLE_MAX_WIDTH, max_lines=3)
    size = int(getattr(font, "size", TITLE_MIN_FONT) or TITLE_MIN_FONT)
    return lines or [value], max(TITLE_MIN_FONT, size)


def _fallback_highlight_text(headline: str) -> str:
    """Pick one conservative exact tail phrase when the semantic director is unavailable."""
    value = str(headline or "").strip()
    total = _canonical(value)
    if len(total) < 8:
        return ""

    # Prefer a short concluding phrase after a late Japanese particle.  In the observed title,
    # this selects ``落とし穴。`` rather than merely coloring the model name.
    for particle in ("の", "は", "が", "を", "に", "で", "と", "：", ":", "、"):
        pos = value.rfind(particle)
        if pos < len(value) // 2:
            continue
        tail = value[pos + 1:].strip()
        canon = _canonical(tail)
        if 4 <= len(canon) <= 14 and len(canon) / max(len(total), 1) <= 0.55:
            return tail

    clauses = [part for part in re.split(r"(?<=[。！？!?])", value) if part.strip()]
    if clauses:
        tail = clauses[-1].strip()
        canon = _canonical(tail)
        if 4 <= len(canon) <= 14 and len(canon) / max(len(total), 1) <= 0.55:
            return tail

    stripped = value.rstrip()
    candidate = stripped[-min(10, max(4, len(stripped) // 3)):]
    canon = _canonical(candidate)
    if 4 <= len(canon) and len(canon) / max(len(total), 1) <= 0.55:
        return candidate
    return ""


def _fallback_plan(title: str) -> tuple[dict[str, Any], str]:
    # Keep the already-approved deterministic public copy boundary: no new facts or rewrite.
    headline = ee.editorial_hook_from_title(title, max_chars=34)
    lines, size = _best_title_layout(headline)
    highlight = _fallback_highlight_text(headline)
    return {
        "eyecatch_title": headline,
        "title_lines": lines,
        "title_font_size": size,
        "title_line_gap": TITLE_LINE_GAP,
    }, highlight


def _has_orange_emphasis(path: str) -> bool:
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            hit = 0
            for pixel in rgb.getdata():
                if all(abs(int(pixel[i]) - HIGHLIGHT_ORANGE[i]) <= 3 for i in range(3)):
                    hit += 1
                    if hit >= 20:
                        return True
    except Exception:
        return False
    return False


def ensure_current_eyecatch_contract(
    title: str,
    summary: str,
    output_path: str,
    *,
    category: str | None = None,
    date_label: str | None = None,
) -> str:
    """Re-render only the foreground typography; the background function is unchanged."""
    plan, highlight = _fallback_plan(title)
    if not highlight:
        return output_path
    return r181._render_balanced_plan(
        title,
        summary,
        output_path,
        plan,
        category=category,
        date_label=date_label,
        highlight_text=highlight,
    )


def repair_public_manuscript(markdown_text: str) -> str:
    """Fix deterministic note presentation defects without touching article semantics."""
    text = str(markdown_text or "")

    # Bare URLs are escaped as text by the note HTML converter; convert only bullets inside
    # the supplemental Evidence section to explicit Markdown anchors.
    section_re = re.compile(
        r"(?ms)(^###\s+補助Evidence\s*$\n)(.*?)(?=^###\s+|^---\s*$|^※|\Z)"
    )

    def evidence_repl(match: re.Match[str]) -> str:
        body = match.group(2)
        body = re.sub(
            r"(?m)^-\s+(https?://[^\s]+)\s*$",
            lambda m: f"- [{m.group(1)}]({m.group(1)})",
            body,
        )
        return match.group(1) + body

    text = section_re.sub(evidence_repl, text)

    # Product terminology is changed only in the subscriber CTA surface, not in article/source text.
    cta_re = re.compile(r"(?ms)(^###\s+調査と判断の時間を減らしたい方へ\s*$.*)\Z")
    match = cta_re.search(text)
    if match:
        cta = match.group(1)
        cta = cta.replace("月次サマリー", "月次ダイジェスト")
        old = (
            "会員向けには、意思決定DBと月次ダイジェストで、"
            "追うべき情報・Evidence・Actionを継続的に整理します。"
        )
        new = (
            "会員向けには、意思決定DBと月次ダイジェストで、公開後も変化を追い、"
            "採用・様子見・見送りの判断に必要なEvidenceとActionを継続的に整理します。"
        )
        cta = cta.replace(old, new)
        text = text[:match.start(1)] + cta
    return text


def extra_reader_value_issues(signals: dict[str, Any]) -> list[str]:
    """Escalate only broad, corroborated reader weakness; one soft signal never blocks Ready."""
    reviewed = [key for key in _CORE_READER_KEYS if signals.get(key) == "REVIEW"]
    issues: list[str] = []
    if len(reviewed) >= 4:
        issues.append(
            READER_VALUE_MARKER
            + "multi_axis_reader_weakness ("
            + "/".join(reviewed)
            + ")"
        )
    if all(
        signals.get(key) == "REVIEW"
        for key in ("accessibility", "jargon_translation", "non_engineer_core_clarity")
    ):
        issues.append(
            READER_VALUE_MARKER
            + "non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity)"
        )
    return list(dict.fromkeys(issues))


def extra_japanese_surface_failures(article: str) -> list[str]:
    prose = re.sub(r"```.*?```|`[^`\n]+`", "", str(article or ""), flags=re.S)
    failures: list[str] = []
    for pattern, reason in _SURFACE_PATTERNS:
        match = pattern.search(prose)
        if match:
            failures.append(
                f"malformed_japanese_surface:{reason}: obvious broken Japanese remains ({match.group(0)})"
            )
    return failures[:5]


def _quality_prompt_suffix() -> str:
    return f"""
[{PROMPT_MARKER} — First Real Publish 最終公開品質]
事実・Evidence・Decisionを変えず、最終稿を『スマホで読む非専門読者』の目で読み直すこと。
- 冒頭で専門用語の説明を積み上げる前に、この情報の意外性・読者への関係・核心のどれかが平易な日本語で早期に伝わるようにする。
- 専門語が続く箇所は、必要なら身近な具体例または平易な言い換えを使い、専門知識がなくても核心まで到達できるようにする。Evidenceにない事実を例として捏造しない。
- 長い説明段落が連続する『報告書の壁』を避け、重複説明・汎用前置き・Decisionに不要な実装細部を削る。短文ノルマや箇条書きノルマは設けない。
- 正しいだけでなく、続きを読みたくなる疑問・発見・具体的な意味が記事固有の流れとして存在するか確認する。
- 最後に助詞衝突、同語の誤重複、誤変換、欠けた述語を読み直し、日本語として不自然な文を残さない。
上記のために新しい数値・人物・引用・因果・導入実績を追加してはいけない。
""".strip()


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_generate_eyecatch = pipeline_module.generate_note_editorial_eyecatch
    original_build_manuscript = pipeline_module.build_clean_note_manuscript
    original_human_appeal = pipeline_module.validate_human_appeal_gate
    original_fact_gate = pipeline_module.validate_fact_gate
    original_prompt = pipeline_module.build_decision_prompt

    def generate_note_editorial_eyecatch(
        title: str,
        summary: str,
        output_path: str,
        category: str | None = None,
        date_label: str | None = None,
    ) -> str:
        path = original_generate_eyecatch(
            title,
            summary,
            output_path,
            category=category,
            date_label=date_label,
        )
        if _has_orange_emphasis(path):
            return path
        try:
            repaired = ensure_current_eyecatch_contract(
                title,
                summary,
                path,
                category=category,
                date_label=date_label,
            )
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.info("[RUN248 EYECATCH] restored current foreground contract after no-orange fallback")
            return repaired
        except Exception as exc:
            # Preserve the already-produced safe image rather than spending a second provider call.
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning("[RUN248 EYECATCH] deterministic foreground repair failed: %s", exc)
            return path

    def build_clean_note_manuscript(*args: Any, **kwargs: Any) -> str:
        return repair_public_manuscript(original_build_manuscript(*args, **kwargs))

    def validate_human_appeal_gate(parsed: dict, peer_articles=None):
        state, issues = original_human_appeal(parsed, peer_articles)
        issues = list(issues or [])
        article = str((parsed or {}).get("note_draft") or "")
        signals = pipeline_module._reader_experience_signals(article) if article else {}
        extra = extra_reader_value_issues(signals)
        if extra:
            issues.extend(item for item in extra if item not in issues)
            if state == "ACCEPTABLE":
                state = "WEAK"
        return state, list(dict.fromkeys(issues))

    def validate_fact_gate(*args: Any, **kwargs: Any):
        ok, failures = original_fact_gate(*args, **kwargs)
        parsed = args[0] if args else kwargs.get("parsed", {})
        article = str((parsed or {}).get("note_draft") or "")
        extra = extra_japanese_surface_failures(article)
        merged = list(dict.fromkeys(list(failures or []) + extra))[:20]
        if extra:
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning("[RUN248 JAPANESE SURFACE] failures=%s", extra)
        return bool(ok) and not extra, merged

    def build_decision_prompt(*args: Any, **kwargs: Any) -> str:
        prompt = original_prompt(*args, **kwargs)
        if PROMPT_MARKER in prompt:
            return prompt
        return prompt.rstrip() + "\n\n" + _quality_prompt_suffix() + "\n"

    pipeline_module.generate_note_editorial_eyecatch = generate_note_editorial_eyecatch
    pipeline_module.build_clean_note_manuscript = build_clean_note_manuscript
    pipeline_module.validate_human_appeal_gate = validate_human_appeal_gate
    pipeline_module.validate_fact_gate = validate_fact_gate
    pipeline_module.build_decision_prompt = build_decision_prompt
    pipeline_module.RUN248_EYECATCH_BACKGROUND_UNCHANGED = True
    pipeline_module.RUN248_ZERO_PROVIDER_CALLS = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
