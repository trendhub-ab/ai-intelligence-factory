"""Run425: restore the mandatory reader-first note intro contract.

A real RubyGems Ready article exposed a late-surface regression: the article body could be
factually sound and still reach Ready without the reader-facing three-part intro that the
reviewed Netflix specimen established.  The canonical public surface is:

    ## どんな内容？
    <one concise what/changed summary>

    **なぜ重要？**
    <why it matters>

    **結論は？**
    <decision / next action>

The old ``何が出た？`` label is intentionally absent; only its summary body is preserved.
Run425 is a zero-provider-call fail-closed contract.  It does not generate missing copy, change
Evidence/Decision, or publish.  Missing/empty/misordered intro content keeps Human Appeal WEAK
before Ready.
"""
from __future__ import annotations

import re
from typing import Any

_INSTALLED_ATTR = "_run425_required_intro_summary_installed"
READER_VALUE_MARKER = "reader_value_review:"
INTRO_HEADING = "どんな内容？"
LEGACY_WHAT_LABEL = "何が出た？"
WHY_LABEL = "なぜ重要？"
DECISION_LABEL = "結論は？"
_REQUIRED_SUMMARY_KEYS = (
    ("what", INTRO_HEADING),
    ("why", WHY_LABEL),
    ("decision", DECISION_LABEL),
)


def _visible(value: str) -> str:
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", str(value or ""))
    text = re.sub(r"[*_`#>\s]+", "", text)
    return text.strip()


def _substantive(value: str) -> bool:
    # A summary row should be a real reader sentence, not a label/fragment placeholder.
    return len(_visible(value)) >= 8


def summary_contract_issues(summary: dict[str, str] | None, projection: str) -> list[str]:
    summary = summary or {}
    issues: list[str] = []
    for key, label in _REQUIRED_SUMMARY_KEYS:
        if not _substantive(str(summary.get(key) or "")):
            issues.append(f"{READER_VALUE_MARKER}final_surface_summary_missing:{label}")

    surface = str(projection or "")
    intro_match = re.search(r"(?m)^##\s+どんな内容？\s*$", surface)
    why_match = re.search(r"(?m)^\*\*なぜ重要？\*\*\s*$", surface)
    decision_match = re.search(r"(?m)^\*\*結論は？\*\*\s*$", surface)
    legacy_match = re.search(r"(?m)^\*\*何が出た？\*\*\s*$", surface)

    if intro_match is None:
        issues.append(f"{READER_VALUE_MARKER}final_surface_intro_heading_missing")
    if why_match is None:
        issues.append(f"{READER_VALUE_MARKER}final_surface_why_label_missing")
    if decision_match is None:
        issues.append(f"{READER_VALUE_MARKER}final_surface_decision_label_missing")
    if legacy_match is not None:
        issues.append(f"{READER_VALUE_MARKER}final_surface_legacy_what_label_present")

    if intro_match and why_match and decision_match:
        if not (intro_match.start() < why_match.start() < decision_match.start()):
            issues.append(f"{READER_VALUE_MARKER}final_surface_intro_order_invalid")
        # The three reader answers must sit before source/evidence/detail sections.
        source_candidates = [
            m.start()
            for pattern in (r"(?m)^###\s+元情報\s*$", r"(?m)^###\s+Sources / Evidence\s*$", r"(?m)^##\s+")
            for m in re.finditer(pattern, surface)
            if m.start() > intro_match.start()
        ]
        later_section = min(source_candidates) if source_candidates else -1
        if later_section >= 0 and decision_match.start() > later_section:
            issues.append(f"{READER_VALUE_MARKER}final_surface_intro_after_detail_section")

    return list(dict.fromkeys(issues))


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_human_appeal = getattr(pipeline_module, "validate_human_appeal_gate", None)
    build_summary = getattr(pipeline_module, "build_reader_first_summary", None)
    build_manuscript = getattr(pipeline_module, "build_clean_note_manuscript", None)
    if not callable(original_human_appeal) or not callable(build_summary) or not callable(build_manuscript):
        return pipeline_module

    def validate_human_appeal_gate_with_required_intro(parsed: dict, peer_articles=None):
        state, issues = original_human_appeal(parsed, peer_articles)
        merged = list(issues or [])
        try:
            summary = dict(build_summary(parsed or {}) or {})
        except Exception:
            summary = {}

        title = str((parsed or {}).get("title_text") or "")
        article = str((parsed or {}).get("note_draft") or "")
        try:
            projection = str(
                build_manuscript(
                    article,
                    title or "preview",
                    "",
                    "",
                    "Unknown",
                    evidence_urls=[],
                    title_text=title,
                    discovery_url="",
                    reader_summary=summary,
                    published_at=None,
                )
                or ""
            )
        except Exception:
            # Fail closed with the same deterministic projection shape used by Run249.
            lines = [f"# {title}", "", "## どんな内容？", ""]
            if summary.get("what"):
                lines.extend([str(summary["what"]), ""])
            if summary.get("why"):
                lines.extend([f"**{WHY_LABEL}**", str(summary["why"]), ""])
            if summary.get("decision"):
                lines.extend([f"**{DECISION_LABEL}**", str(summary["decision"]), ""])
            if article:
                lines.append(article)
            projection = "\n".join(lines).strip()

        extra = summary_contract_issues(summary, projection)
        if extra:
            merged.extend(item for item in extra if item not in merged)
            state = "WEAK"
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning("[RUN425 REQUIRED INTRO] issues=%s", extra)
        return state, list(dict.fromkeys(merged))

    pipeline_module.validate_human_appeal_gate = validate_human_appeal_gate_with_required_intro
    pipeline_module.RUN425_REQUIRED_INTRO_SUMMARY = True
    pipeline_module.RUN425_ZERO_PROVIDER_CALLS = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
