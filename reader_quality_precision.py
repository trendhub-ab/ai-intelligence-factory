"""Run275 zero-API reader-quality precision overlay.

Real ONE-SHOT Run31 produced three evidence-sufficient manuscripts but Ready=0. Artifact
falsification showed two different causes mixed together: genuine dense technical prose and
narrow reader diagnostics that could misclassify valid reader bridges, visible heading breaks,
or later acronym explanations. This overlay corrects only those reproducible false positives.
It does not relax Fact/Evidence/Publication gates, create model/provider calls, or turn genuinely
dense prose into GOOD.
"""
from __future__ import annotations

import re
from typing import Any

_INSTALL_FLAG = "_run275_reader_quality_precision_installed"
READER_VALUE_MARKER = "reader_value_review:"

_PULL_MARKERS_RE = re.compile(
    r"(?:[？?]|たとえば|例えば|もし|ところが|一方|逆に|意外|実際|場面|朝\d{0,2}時|困る|怖い|変わる|比べ|なのに)"
)
_STRONG_OPENING_BRIDGE_RE = re.compile(
    r"(?:[？?]|でしょうか|ませんか|ありますか|ありますよね|ですよね|"
    r"たとえば|例えば|もし|スマホ|買い物|旅行|学校|家族|仕事で|使う側|"
    r"普通の言葉|簡単に言えば|要するに|意外|困った|迷った|"
    r"(?:あなた|私たち)[^。！？]{0,90}(?:不安|困|迷|課題|悩|障壁|懸念|選択|使|導入))"
)
_GA_NI_COLLISION_RE = re.compile(
    r"がに(?=(?:減少|増加|向上|低下|改善|悪化|変化)(?:し|する|した|します|しました))"
)


def _heading_aware_max_explanatory_run(article: str) -> int:
    """Count uninterrupted dense explanatory paragraphs while treating headings as breaks."""
    current = 0
    maximum = 0
    for block in re.split(r"\n\s*\n", str(article or "")):
        value = block.strip()
        if not value:
            continue
        if re.match(r"^#{1,6}\s+", value):
            current = 0
            # A heading can share a block with prose in malformed Markdown. Only inspect the
            # remaining text; the visible heading still breaks the previous explanatory run.
            value = re.sub(r"^#{1,6}\s+[^\n]*(?:\n|$)", "", value, count=1).strip()
            if not value:
                continue
        compact = re.sub(r"\s+", "", value)
        is_explain = len(compact) >= 90 and not _PULL_MARKERS_RE.search(value)
        if is_explain:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def _opening_has_strong_reader_bridge(article: str) -> bool:
    text = re.sub(r"^#{1,6}\s+.*$", "", str(article or ""), flags=re.MULTILINE)
    opening = re.sub(r"\s+", " ", text[:1100]).strip()
    return bool(_STRONG_OPENING_BRIDGE_RE.search(opening))


def _token_explained_anywhere(token: str, article: str) -> bool:
    value = str(article or "")
    escaped = re.escape(token)
    # Python's Unicode \b treats Japanese particles as word characters. Use ASCII-only
    # boundaries so forms such as ``CLIを`` and ``CLI（...）`` are recognized correctly
    # without weakening matching inside longer ASCII identifiers.
    ascii_token = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    patterns = (
        rf"{ascii_token}\s*[（(][^）)\n]{{2,90}}[）)]",
        rf"[（(][^）)\n]{{2,90}}[）)]\s*{ascii_token}",
        rf"[^。！？\n]{{3,90}}[（(]{escaped}[）)]",
        rf"{ascii_token}(?:とは|は、|は)[^。！？\n]{{4,110}}(?:仕組み|方式|規格|標準|ツール|モデル|プロトコル|ルール|方法|役割)",
    )
    return any(re.search(pattern, value, re.I) for pattern in patterns)


def _token_is_stable_compound_label(token: str, article: str) -> bool:
    """Ignore a two-letter token only when every occurrence belongs to one stable label.

    This is deliberately narrower than a global acronym allowlist. It covers entity labels such
    as ``VT Code`` or ``LM Studio`` while keeping standalone technical acronyms such as VRAM/MCP.
    """
    if len(token) != 2 or not token.isupper():
        return False
    matches = list(re.finditer(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", str(article or "")))
    if not matches:
        return False
    followers: list[str] = []
    for match in matches:
        tail = str(article or "")[match.end():match.end() + 40]
        # Same Unicode-boundary rule as above: ``Codeを`` / ``Studio側`` are valid
        # Japanese continuations of an ASCII entity label and must not fail on \b.
        follower = re.match(r"\s+([A-Z][a-z][A-Za-z0-9.+-]{1,24})(?![A-Za-z0-9])", tail)
        if not follower:
            return False
        followers.append(follower.group(1))
    return len(set(followers)) == 1


def _correct_unexplained_jargon(base: dict[str, Any], article: str) -> list[str]:
    corrected: list[str] = []
    for raw in list(base.get("unexplained_jargon") or []):
        token = str(raw or "").strip()
        if not token or token == "PC":
            continue
        if _token_explained_anywhere(token, article):
            continue
        if _token_is_stable_compound_label(token, article):
            continue
        corrected.append(token)
    return corrected[:8]


def correct_reader_signals(article: str, original: dict[str, Any]) -> dict[str, Any]:
    """Apply only deterministic Run31-derived precision corrections to an existing signal set."""
    signals = dict(original or {})
    if not signals:
        return signals

    technical_density = float(signals.get("technical_terms_per_1000_chars") or 0.0)
    opening_density = float(signals.get("opening_technical_terms_per_1000_chars") or 0.0)
    plain_bridge = bool(signals.get("plain_language_bridge_present"))
    dense_paragraphs = int(signals.get("jargon_dense_paragraph_count") or 0)
    implementation_count = int(signals.get("implementation_identifier_count") or 0)
    analogy_hits = int(signals.get("analogy_hits") or 0)

    corrected_jargon = _correct_unexplained_jargon(signals, article)
    signals["unexplained_jargon"] = corrected_jargon
    bridge_needed = bool(corrected_jargon) or technical_density >= 26.0
    signals["bridge_needed"] = bridge_needed
    signals["analogy_necessary"] = (
        signals.get("analogy_necessary")
        if bool(signals.get("analogy_used"))
        else ("BRIDGE_RECOMMENDED" if bridge_needed and not plain_bridge else "NOT_REQUIRED")
    )

    if opening_density < 42.0 and (_opening_has_strong_reader_bridge(article) or not bridge_needed):
        signals["opening_non_engineer_access"] = "GOOD"

    heading_run = _heading_aware_max_explanatory_run(article)
    signals["max_explanatory_paragraph_run"] = heading_run
    signals["reader_temperature_rhythm"] = "GOOD" if heading_run <= 2 else "REVIEW"
    if heading_run <= 2:
        signals["narrative_pull"] = "GOOD"

    jargon_translation = "GOOD" if not (bridge_needed and not plain_bridge) and dense_paragraphs <= 1 else "REVIEW"
    signals["jargon_translation"] = jargon_translation
    signals["non_engineer_core_clarity"] = (
        "GOOD" if jargon_translation == "GOOD" and (not bridge_needed or plain_bridge) else "REVIEW"
    )
    signals["plain_language_bridge"] = "GOOD" if plain_bridge or not bridge_needed else "REVIEW"

    issues = [
        str(item)
        for item in list(signals.get("accessibility_issues") or [])
        if str(item) not in {
            "unexplained_acronyms",
            "plain_language_bridge_missing",
            "jargon_translation_weak",
            "opening_non_engineer_access_weak",
            "reader_temperature_rhythm_weak",
        }
    ]
    if corrected_jargon:
        issues.append("unexplained_acronyms")
    if bridge_needed and not plain_bridge:
        issues.append("plain_language_bridge_missing")
    if jargon_translation != "GOOD":
        issues.append("jargon_translation_weak")
    if signals.get("opening_non_engineer_access") != "GOOD":
        issues.append("opening_non_engineer_access_weak")
    if signals.get("reader_temperature_rhythm") != "GOOD":
        issues.append("reader_temperature_rhythm_weak")
    signals["accessibility_issues"] = list(dict.fromkeys(issues))
    signals["accessibility"] = "GOOD" if not signals["accessibility_issues"] else "REVIEW"

    enjoyment = [
        str(item)
        for item in list(signals.get("enjoyment_issues") or [])
        if not (str(item) == "explanation_run_long" and heading_run < 4)
    ]
    signals["enjoyment_issues"] = list(dict.fromkeys(enjoyment))
    signals["reader_enjoyment"] = "GOOD" if not signals["enjoyment_issues"] else "REVIEW"

    # Only upgrade Information Budget when every known trigger is absent after the heading-aware
    # correction. A genuinely jargon-dense manuscript therefore remains REVIEW.
    if signals.get("information_budget") == "REVIEW":
        no_known_budget_trigger = (
            dense_paragraphs < 3
            and not (analogy_hits >= 3 and technical_density >= 30.0)
            and not (heading_run >= 4 and technical_density >= 26.0)
            and not (implementation_count >= 10 and dense_paragraphs >= 2)
        )
        if no_known_budget_trigger:
            signals["information_budget"] = "GOOD"

    signals["run275_precision_overlay"] = True
    return signals


def _malformed_surface_issue(article: str) -> str:
    prose = re.sub(r"```.*?```|`[^`\n]+`", "", str(article or ""), flags=re.S)
    if _GA_NI_COLLISION_RE.search(prose):
        return READER_VALUE_MARKER + "final_surface_malformed_japanese_surface:particle_collision_ga_ni"
    return ""


def install(pipeline_module: Any) -> Any:
    """Install after historical reader/final-surface layers; zero API and idempotent.

    Run231 regression doubles deliberately expose only a minimal Production entrypoint. Run275
    must therefore be optional on those doubles while remaining active when the real reader
    surfaces exist.
    """
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module

    original_signals = getattr(pipeline_module, "_reader_experience_signals", None)
    original_human_appeal = getattr(pipeline_module, "validate_human_appeal_gate", None)

    if callable(original_signals):
        def corrected_signals(article: str) -> dict[str, Any]:
            return correct_reader_signals(article, original_signals(article))
        pipeline_module._reader_experience_signals = corrected_signals

    if callable(original_human_appeal):
        def validate_with_surface_precision(parsed: dict, peer_articles=None):
            state, issues = original_human_appeal(parsed, peer_articles)
            merged = list(issues or [])
            issue = _malformed_surface_issue(str((parsed or {}).get("note_draft") or ""))
            if issue and issue not in merged:
                merged.append(issue)
                state = "WEAK"
            return state, merged
        pipeline_module.validate_human_appeal_gate = validate_with_surface_precision

    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
