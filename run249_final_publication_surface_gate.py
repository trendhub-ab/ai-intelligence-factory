"""Run249/276: final publication-surface revalidation before Ready.

Run248 proved that reader-value diagnostics can stop weak generated drafts, but the first
post-Run248 real article exposed a later boundary: the reader-first summary/title/presentation
surface is assembled only after the normal article gates. A draft can therefore pass the
article gate and still become a weak or malformed final note manuscript.

Run32 exposed an important category boundary. The final projection prepends three intentionally
compact 30-second summary answers to the article. Feeding that combined surface back through the
full long-form article density/rhythm diagnostics can manufacture Jargon/Information-Budget
reviews even when the article body itself is healthy: two 70-110 character summary rows are
enough to look like two dense "article paragraphs". Run276 keeps final-surface protection but
uses the article body as authority for article-wide Reader axes and applies narrow, high-confidence
summary checks to the compact header itself.

This layer stays zero-provider-call. It also repairs one deterministic presentation-only defect
(the canonical disclaimer being glued to a supplemental Evidence link). No Evidence, Decision,
numerical claim, model call, eyecatch background, or public release behavior is changed.
"""
from __future__ import annotations

import re
from typing import Any

_INSTALLED_ATTR = "_run249_final_publication_surface_gate_installed"
READER_VALUE_MARKER = "reader_value_review:"
RUN249_ZERO_PROVIDER_CALLS = True
RUN276_SUMMARY_AWARE_FINAL_SURFACE = True

_SUMMARY_LABELS = (
    ("what", "何が出た？"),
    ("why", "なぜ重要？"),
    ("decision", "結論は？"),
)

# Article-wide Reader dimensions. These belong to the long-form body; Run276 does not let the
# compact 30-second header redefine them merely because it is prepended to the final surface.
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

_SURFACE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"をに(?=(?:速|遅|高|低|大|小|強|弱|増|減|変|近|遠|広|狭|長|短|重|軽))"),
        "particle_collision_wo_ni",
    ),
    (re.compile(r"主主要"), "duplicated_primary_modifier"),
    (re.compile(r"眼砲"), "malformed_lexeme_ganpou"),
)

_SUMMARY_COMMON_ACRONYMS = {
    "AI", "API", "LLM", "OSS", "URL", "UI", "UX", "DB", "CPU", "GPU", "ID", "PC",
}
_SUMMARY_PLAIN_BRIDGE_RE = re.compile(
    r"(?:簡単に言えば|ひと言で言えば|一言で言えば|平たく言えば|要するに|つまり|"
    r"言葉を変えると|たとえば|例えば|ようなもの|という意味|を指します|のことです)"
)


def _extra_reader_value_issues(signals: dict[str, Any]) -> list[str]:
    """Broad long-form reader weakness over the article body."""
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


def _extra_japanese_surface_failures(article: str) -> list[str]:
    """High-confidence Japanese surface defects, zero dependency."""
    prose = re.sub(r"```.*?```|`[^`\n]+`", "", str(article or ""), flags=re.S)
    failures: list[str] = []
    for pattern, reason in _SURFACE_PATTERNS:
        match = pattern.search(prose)
        if match:
            failures.append(
                f"malformed_japanese_surface:{reason}: obvious broken Japanese remains ({match.group(0)})"
            )
    return failures[:5]


def _unbalanced_japanese_quote_issue(title: str) -> str:
    """Return one high-confidence title punctuation defect, otherwise empty string."""
    value = str(title or "")
    for opener, closer, label in (("「", "」", "kagi"), ("『", "』", "double_kagi")):
        depth = 0
        for char in value:
            if char == opener:
                depth += 1
            elif char == closer:
                if depth <= 0:
                    return f"{READER_VALUE_MARKER}final_surface_title_unbalanced_{label}"
                depth -= 1
        if depth:
            return f"{READER_VALUE_MARKER}final_surface_title_unbalanced_{label}"
    return ""


def _summary_fragment_issues(summary: dict[str, str] | None) -> list[str]:
    """Detect only obvious reader-summary fragments; do not guess Japanese grammar broadly."""
    summary = summary or {}
    issues: list[str] = []
    for key, label in _SUMMARY_LABELS:
        value = str(summary.get(key) or "").strip()
        if not value:
            continue
        if re.search(r"[、，,]\s*$", value):
            issues.append(
                f"{READER_VALUE_MARKER}final_surface_summary_fragment:{label}"
            )
    return issues


def _summary_row_is_jargon_dense(value: str) -> bool:
    """High-confidence compact-summary jargon signal, not a long-form paragraph metric."""
    text = re.sub(r"\[([^]]+)\]\([^)]*\)|[*_`#]", r"\1", str(value or ""))
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 45 or _SUMMARY_PLAIN_BRIDGE_RE.search(text):
        return False

    acronyms = {
        token for token in re.findall(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9-]{1,8})(?![A-Za-z0-9])", text)
        if token not in _SUMMARY_COMMON_ACRONYMS
    }
    technical = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_.+/#-]{2,}|[ァ-ヴー]{5,}", text)
    }
    # This threshold is intentionally much narrower than the article diagnostic. A compact
    # answer is allowed to be information-dense; we block only a cluster with multiple uncommon
    # acronyms or many distinct technical terms and no plain-language bridge.
    return len(acronyms) >= 2 or len(technical) >= 5


def _summary_reader_value_issues(summary: dict[str, str] | None) -> list[str]:
    summary = summary or {}
    dense_labels = [
        label for key, label in _SUMMARY_LABELS
        if _summary_row_is_jargon_dense(str(summary.get(key) or ""))
    ]
    if len(dense_labels) >= 2:
        return [
            READER_VALUE_MARKER
            + "final_surface_summary_jargon_cluster ("
            + "/".join(dense_labels)
            + ")"
        ]
    return []


def _projection_from_parts(title: str, summary: dict[str, str], article: str) -> str:
    lines = [f"# {str(title or '').strip()}", "", "## 30秒でわかるこの記事", ""]
    for key, label in _SUMMARY_LABELS:
        value = str((summary or {}).get(key) or "").strip()
        if value:
            lines.extend([f"**{label}**", value, ""])
    if article:
        lines.append(str(article).strip())
    return "\n".join(lines).strip()


def _final_surface_probe(
    pipeline_module: Any,
    original_build_manuscript,
    parsed: dict,
    reader_summary: dict[str, str],
) -> str:
    """Build a deterministic close proxy of the later persisted note surface."""
    title = str((parsed or {}).get("title_text") or "")
    article = str((parsed or {}).get("note_draft") or "")
    try:
        return str(
            original_build_manuscript(
                article,
                title or "preview",
                "",
                "",
                "Unknown",
                evidence_urls=[],
                title_text=title,
                discovery_url="",
                reader_summary=reader_summary,
                published_at=None,
            )
            or ""
        )
    except Exception:
        return _projection_from_parts(title, reader_summary, article)


def final_surface_issues(
    pipeline_module: Any,
    original_build_manuscript,
    original_build_summary,
    parsed: dict,
) -> tuple[list[str], dict[str, str], str]:
    """Return material issues for the final public projection, zero API.

    Run276 separates two domains:
    - article-wide Reader axes are evaluated on the actual article body;
    - late title/summary/presentation defects are evaluated with surface-specific checks.
    The final projection is still scanned for malformed Japanese, so presentation assembly cannot
    hide a broken public sentence.
    """
    parsed = parsed or {}
    issues: list[str] = []

    title_issue = _unbalanced_japanese_quote_issue(str(parsed.get("title_text") or ""))
    if title_issue:
        issues.append(title_issue)

    try:
        summary = dict(original_build_summary(parsed) or {})
    except Exception:
        summary = {}
    issues.extend(_summary_fragment_issues(summary))
    issues.extend(_summary_reader_value_issues(summary))

    projection = _final_surface_probe(
        pipeline_module, original_build_manuscript, parsed, summary
    )

    article = str(parsed.get("note_draft") or "")
    if article:
        signals = pipeline_module._reader_experience_signals(article)
        for issue in _extra_reader_value_issues(signals):
            suffix = str(issue).split(READER_VALUE_MARKER, 1)[-1]
            issues.append(READER_VALUE_MARKER + "final_surface_" + suffix)

    if projection:
        for failure in _extra_japanese_surface_failures(projection):
            issues.append(READER_VALUE_MARKER + "final_surface_" + str(failure))

    return list(dict.fromkeys(issues)), summary, projection


def repair_final_public_manuscript(markdown_text: str) -> str:
    """Repair deterministic presentation-only defects after Run248 manuscript shaping."""
    text = str(markdown_text or "")
    text = re.sub(
        r"(?<!\n)(?=※本記事に含まれる見解・提案は筆者個人の意見であり、)",
        "\n\n",
        text,
    )
    return text


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_human_appeal = pipeline_module.validate_human_appeal_gate
    original_build_manuscript = pipeline_module.build_clean_note_manuscript
    original_build_summary = pipeline_module.build_reader_first_summary

    def validate_human_appeal_gate_with_final_surface(parsed: dict, peer_articles=None):
        state, issues = original_human_appeal(parsed, peer_articles)
        merged = list(issues or [])
        extra, summary, projection = final_surface_issues(
            pipeline_module,
            original_build_manuscript,
            original_build_summary,
            parsed,
        )
        if extra:
            merged.extend(item for item in extra if item not in merged)
            state = "WEAK"
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning(
                    "[RUN249 FINAL SURFACE REVIEW] issues=%s summary=%s chars=%s",
                    extra,
                    {key: len(str(value or "")) for key, value in summary.items()},
                    len(projection),
                )
        return state, list(dict.fromkeys(merged))

    def build_clean_note_manuscript_with_final_presentation_repair(*args: Any, **kwargs: Any) -> str:
        return repair_final_public_manuscript(original_build_manuscript(*args, **kwargs))

    pipeline_module.validate_human_appeal_gate = validate_human_appeal_gate_with_final_surface
    pipeline_module.build_clean_note_manuscript = build_clean_note_manuscript_with_final_presentation_repair
    pipeline_module.RUN249_ZERO_PROVIDER_CALLS = True
    pipeline_module.RUN249_FINAL_SURFACE_REVALIDATION = True
    pipeline_module.RUN276_SUMMARY_AWARE_FINAL_SURFACE = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module