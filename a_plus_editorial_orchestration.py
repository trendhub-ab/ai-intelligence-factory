"""A+ runtime orchestration: Local Skills skeleton, Gemini prose, provider-free retry fallback.

This layer is deliberately external to pipeline.py so the production core remains small.
It changes no Gate thresholds, adds no mandatory provider call, and never creates a
Decision when the initial Deep Dive failed before structured management data existed.
"""
from __future__ import annotations

import re
from functools import wraps
from types import SimpleNamespace
from typing import Any

from editorial_naturalness import build_naturalness_retry_contract as _base_naturalness_retry_contract

from local_skills.a_plus import (
    build_prewrite_contract,
    can_use_local_fallback,
    render_provider_compatible_fallback,
    repair_unbalanced_japanese_quotes,
)


_MARKER = "_a_plus_editorial_orchestration_installed"
_OUTPUT_MARKER = "\n【Output Contract｜完成稿のみ】"
_EXCLUDED_NATURALNESS_HEADINGS = {
    "Reader-first summary", "Reader Summary", "どんな内容？", "なぜ重要？",
    "結論は？", "元情報", "Sources / Evidence", "Sources", "Evidence",
}


def _ready_corpus_sections(text: str) -> list[tuple[int, str]]:
    """Return authorial H2/H3 prose while ignoring quotes, code and metadata blocks."""
    lines: list[str] = []
    fence: str | None = None
    for line in (text or "").splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if re.fullmatch(r"\s{0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = None
            lines.append("")
            continue
        if marker:
            fence = marker.group(1)
            lines.append("")
            continue
        lines.append("" if re.match(r"^\s*>", line) else line)

    body = "\n".join(lines)
    body = re.sub(r"`[^`\n]*`|「[^」]*」|『[^』]*』", "引用", body)
    headings = list(re.finditer(r"^(#{2,3})\s+(.+)$", body, re.M))
    sections: list[tuple[int, str]] = []
    excluded_level: int | None = None
    for index, match in enumerate(headings):
        level = len(match.group(1))
        if excluded_level is not None and level <= excluded_level:
            excluded_level = None
        if match.group(2).strip() in _EXCLUDED_NATURALNESS_HEADINGS:
            excluded_level = level
        if excluded_level is not None:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        prose = body[match.end():end].strip()
        if prose:
            sections.append((index + 1, prose))
    return sections


def ready_corpus_naturalness_signals(text: str) -> dict:
    """Advisory-only signals derived from actual Ready manuscripts.

    Each habit must repeat across at least two sections. Repair is recommended only
    when two independent habit classes repeat together, so isolated editorial emphasis
    remains untouched.
    """
    dramatic_sections: list[int] = []
    abstract_closing_sections: list[int] = []
    dramatic_patterns = (
        r"今回(?:注目すべき|重要なの|の変化|のポイント)",
        r"単なる[^。！？\n]{0,60}(?:だけではありません|ではありません|ではない)",
        r"単に[^。！？\n]{0,60}(?:という話ではありません|という話ではない)",
        r"ここで(?:一つの)?(?:緊張感|重要なの|重要な|ポイント|問題|境界線)",
    )
    abstract_closing_pattern = re.compile(
        r"(?:ことを示唆しています|ことを示しています|証左(?:だ|です|と言えます)|"
        r"フェーズに入ったと言えます|スタンダード[^。！？\n]{0,35}(?:近道|と言えます)|"
        r"へと変質し始めていることを示唆しています)[。！？!?]?$"
    )
    for number, prose in _ready_corpus_sections(text):
        if any(re.search(pattern, prose) for pattern in dramatic_patterns):
            dramatic_sections.append(number)
        sentences = [s.strip() for s in re.split(r"(?<=[。！？!?])|\n", prose) if s.strip()]
        closing = sentences[-1] if sentences else ""
        if abstract_closing_pattern.search(closing):
            abstract_closing_sections.append(number)

    signals = {
        "repeated_dramatic_scaffolding": dramatic_sections if len(dramatic_sections) >= 2 else [],
        "repeated_abstract_closings": abstract_closing_sections if len(abstract_closing_sections) >= 2 else [],
    }
    signals["repair_recommended"] = sum(bool(value) for value in signals.values()) >= 2
    return signals


def build_ready_corpus_naturalness_retry_contract(article: str) -> str:
    """Enrich an already-authorized retry; never authorize or schedule another call."""
    base = _base_naturalness_retry_contract(article)
    signals = ready_corpus_naturalness_signals(article)
    if not signals["repair_recommended"]:
        return base

    advice = [
        "[naturalness-v2｜実Ready稿由来の補助指示]",
        "検出は編集上の目安であり、新しい不合格理由ではない。",
    ]
    if signals["repeated_dramatic_scaffolding"]:
        sections = ", ".join(map(str, signals["repeated_dramatic_scaffolding"]))
        advice.append(
            f"・節 {sections}: 『今回注目すべき』『単なるAではなくB』『ここで〜』のようなドラマ化したメタ説明を減らし、事実を直接置く。"
        )
    if signals["repeated_abstract_closings"]:
        sections = ", ".join(map(str, signals["repeated_abstract_closings"]))
        advice.append(
            f"・節 {sections}: 『示唆する』『証左と言える』など抽象的な節末総括の反復を減らし、根拠のある具体判断だけを残す。"
        )
    advice.extend([
        "自然な単発表現は残す。Fact / Evidence / Decision・数値・URL・条件・制約・情報量を維持し、文章の運びだけを直す。",
        "既存Gateの修正を優先する。追加生成や再試行を要求しない。",
    ])
    supplement = "\n".join(advice)
    return base + ("\n\n" if base else "") + supplement


def _provider_unavailable(exc: Exception) -> bool:
    name = exc.__class__.__name__
    if name in {
        "GeminiCallTimeoutError",
        "NoAvailableModelError",
        "GeminiBudgetExceededError",
        "DeepDiveRunBudgetExceededError",
        "PendingRetryBudgetExceededError",
    }:
        return True
    return getattr(exc, "code", None) in {429, 503}


def _fallback_grounding(source_info: dict) -> dict[str, Any]:
    primary = str(source_info.get("primary_url") or "").strip()
    urls: list[str] = []
    for value in list(source_info.get("evidence_urls") or []):
        url = str(value or "").strip()
        if url and url not in urls:
            urls.append(url)
    if primary and primary not in urls:
        urls.append(primary)
    return {
        "grounding_status": str(source_info.get("method") or "Source Native"),
        "evidence_urls": urls,
        "a_plus_local_fallback": True,
    }


def install(pipeline_module):
    p = pipeline_module
    if bool(getattr(p, _MARKER, False)):
        return p

    original_prompt = p.build_decision_prompt
    original_parse = p._parse_gemini_response
    original_retry = p.should_attempt_dynamic_retry
    original_call = p.call_gemini_grounded_deep_dive
    original_generate = p.generate_intelligence_report

    state: dict[str, Any] = {
        "last_parsed": None,
        "last_retry_rows": [],
        "last_evidence_result": {},
        "force_local_fallback": False,
        "retry_article": "",
    }

    @wraps(original_generate)
    def generate_intelligence_report_a_plus(*args, **kwargs):
        state["last_parsed"] = None
        state["last_retry_rows"] = []
        state["last_evidence_result"] = {}
        state["force_local_fallback"] = False
        state["retry_article"] = ""
        return original_generate(*args, **kwargs)

    @wraps(original_prompt)
    def build_decision_prompt_a_plus(*args, **kwargs):
        prompt = str(original_prompt(*args, **kwargs) or "")
        state["retry_article"] = str(kwargs.get("previous_article") or "")
        evidence_result = kwargs.get("evidence_result") or {}
        evidence_metadata = kwargs.get("evidence_metadata") or {}
        contract = build_prewrite_contract(evidence_result, evidence_metadata)
        block = "\n【A+ Local Skills Pre-Write Contract】\n" + contract + "\n"
        if _OUTPUT_MARKER in prompt:
            return prompt.replace(_OUTPUT_MARKER, block + _OUTPUT_MARKER, 1)
        return prompt.rstrip() + "\n" + block

    @wraps(original_parse)
    def parse_gemini_response_a_plus(*args, **kwargs):
        parsed = original_parse(*args, **kwargs)
        if isinstance(parsed, dict):
            original_title = str(parsed.get("title_text") or "")
            repaired_title = repair_unbalanced_japanese_quotes(original_title)
            if repaired_title and repaired_title != original_title:
                parsed = dict(parsed)
                parsed["title_text"] = repaired_title
                logger = getattr(p, "logger", None)
                if logger:
                    logger.info("[A+ TITLE PUNCTUATION REPAIR] unmatched Japanese quote removed")
            state["last_parsed"] = dict(parsed)
        return parsed

    @wraps(original_retry)
    def should_attempt_dynamic_retry_a_plus(reason_rows, evidence_result, *args, **kwargs):
        rows = list(reason_rows or [])
        evidence = dict(evidence_result or {})
        state["last_retry_rows"] = rows
        state["last_evidence_result"] = evidence
        state["force_local_fallback"] = False

        allowed, reason = original_retry(reason_rows, evidence_result, *args, **kwargs)
        if allowed:
            return allowed, reason

        seed = state.get("last_parsed")
        if can_use_local_fallback(seed, rows, evidence):
            state["force_local_fallback"] = True
            return True, "a_plus_local_fallback"
        return allowed, reason

    @wraps(original_call)
    def call_gemini_grounded_deep_dive_a_plus(
        prompt: str,
        repo: dict,
        source_info: dict,
        request_kind: str = "deep_dive",
        request_context: str = "",
        request_origin: str = "new",
    ):
        def local_result(cause: str):
            seed = state.get("last_parsed")
            rows = list(state.get("last_retry_rows") or [])
            evidence = dict(
                state.get("last_evidence_result")
                or source_info.get("evidence_result")
                or {}
            )
            if request_kind != "quality_retry" or not can_use_local_fallback(seed, rows, evidence):
                return None
            response_text, meta = render_provider_compatible_fallback(
                p,
                repo,
                seed,
                source_info=source_info,
            )
            logger = getattr(p, "logger", None)
            if logger:
                logger.warning(
                    "[A+ LOCAL FALLBACK] %s cause=%s writer=%s provider_article_reused=%s",
                    request_context,
                    cause,
                    meta.get("writer_blob_sha"),
                    meta.get("provider_article_surface_reused"),
                )
            return (
                SimpleNamespace(text=response_text, candidates=[]),
                _fallback_grounding(source_info),
            )

        if request_kind == "quality_retry" and bool(state.get("force_local_fallback")):
            result = local_result("retry_policy_unavailable")
            if result is not None:
                state["force_local_fallback"] = False
                return result

        if request_kind == "quality_retry":
            advice = build_ready_corpus_naturalness_retry_contract(state["retry_article"])
            if advice:
                prompt = prompt.rstrip() + "\n\n" + advice

        try:
            return original_call(
                prompt,
                repo,
                source_info,
                request_kind=request_kind,
                request_context=request_context,
                request_origin=request_origin,
            )
        except Exception as exc:
            if request_kind == "quality_retry" and _provider_unavailable(exc):
                result = local_result(
                    f"provider_unavailable:{exc.__class__.__name__}"
                )
                if result is not None:
                    state["force_local_fallback"] = False
                    return result
            raise

    p.generate_intelligence_report = generate_intelligence_report_a_plus
    p.build_decision_prompt = build_decision_prompt_a_plus
    p._parse_gemini_response = parse_gemini_response_a_plus
    p.should_attempt_dynamic_retry = should_attempt_dynamic_retry_a_plus
    p.call_gemini_grounded_deep_dive = call_gemini_grounded_deep_dive_a_plus
    setattr(p, _MARKER, True)
    setattr(p, "A_PLUS_EDITORIAL_ORCHESTRATION", True)
    return p
