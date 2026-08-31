"""Run173 operational yield guardrails.

Two zero/new-quota reliability fixes derived from production audit:
1) stop repeatedly waiting on the same model after consecutive unobserved transport timeouts;
2) allow the existing deterministic publication rescue to remove a narrowly diagnosed
   unsupported vague quantity sentence (for example ``数倍``) without another model call.

The module never weakens Fact/Evidence gates. Any rescued manuscript still goes through the
existing publication-rescue revalidation path in pipeline.py.
"""
from __future__ import annotations

import copy
import os
import re
from typing import Any

_INSTALLED_ATTR = "_run173_operational_yield_installed"
_TIMEOUT_STREAK_ATTR = "_run173_transport_timeout_streaks"
_DEFAULT_TIMEOUT_THRESHOLD = 2

_VAGUE_QUANTIFIED_REASON_RE = re.compile(
    r"unsupported\s+vague\s+quantified\s+claim\s*:\s*([^\s,，。;；]+)", re.I
)
# Keep this deliberately narrow. Exact numeric claims are already handled by the core
# deterministic rescue. These are the Japanese vague-quantity forms observed by the gate.
_SAFE_VAGUE_TOKENS_RE = re.compile(
    r"^(?:数(?:十|百|千|万)?倍|数年|数(?:ヶ|か)?月|数週(?:間)?|数日|数時間|数分|数秒|数[%％])$"
)


def _timeout_threshold() -> int:
    raw = os.environ.get("GEMINI_MODEL_TIMEOUT_CIRCUIT_BREAKER_THRESHOLD", str(_DEFAULT_TIMEOUT_THRESHOLD))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = _DEFAULT_TIMEOUT_THRESHOLD
    return max(1, min(5, value))


def _reason_message(row: dict) -> str:
    return str((row or {}).get("message") or (row or {}).get("reason") or "").strip()


def _diagnosed_vague_tokens(reason_rows: list[dict]) -> list[str]:
    tokens: list[str] = []
    for row in reason_rows or []:
        code = str((row or {}).get("reason_code") or "")
        if code and code != "FACT_UNSUPPORTED_CLAIM":
            continue
        match = _VAGUE_QUANTIFIED_REASON_RE.search(_reason_message(row))
        if not match:
            continue
        token = match.group(1).strip("'\"[]()（）")
        if _SAFE_VAGUE_TOKENS_RE.fullmatch(token) and token not in tokens:
            tokens.append(token)
    return tokens[:2]


def _protected_text(parsed: dict) -> str:
    keys = (
        "title", "article_title", "note_title", "title_text",
        "action", "action_text", "next_action", "next_action_text",
    )
    return "\n".join(str((parsed or {}).get(key) or "") for key in keys)


def _remove_vague_quantity_sentences(draft: str, tokens: list[str]) -> tuple[str, list[str]]:
    """Delete only prose sentences containing already-diagnosed vague quantity tokens.

    Headings and list items are never modified. At most two sentences may be removed and the
    result must retain >=85% of the original manuscript, keeping this a true micro rescue.
    """
    text = str(draft or "")
    if not text or not tokens:
        return text, []

    removed: list[str] = []
    out_lines: list[str] = []
    for line in text.splitlines():
        if len(removed) >= 2 or not any(token in line for token in tokens):
            out_lines.append(line)
            continue
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or re.match(r"^(?:[-*•・]|\d+[.)．])\s*", stripped):
            out_lines.append(line)
            continue

        # Preserve punctuation with each sentence so unaffected prose is byte-close to source.
        parts = re.findall(r".*?(?:[。！？!?]+|$)", line)
        parts = [part for part in parts if part]
        kept: list[str] = []
        for part in parts:
            matched = next((token for token in tokens if token in part), None)
            if matched and len(removed) < 2:
                removed.append(matched)
                continue
            kept.append(part)
        out_lines.append("".join(kept).strip())

    candidate = "\n".join(out_lines)
    candidate = re.sub(r"\n{3,}", "\n\n", candidate).strip()
    if not removed:
        return text, []
    if len(candidate) < max(500, int(len(text) * 0.85)):
        return text, []
    return candidate, removed


def install(pipeline_module: Any) -> Any:
    """Install Run173 wrappers idempotently on top of Run172."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_generate = pipeline_module._generate_via_chat
    original_rescue = pipeline_module._apply_deterministic_publication_rescue
    streaks: dict[str, int] = getattr(pipeline_module, _TIMEOUT_STREAK_ATTR, {}) or {}
    setattr(pipeline_module, _TIMEOUT_STREAK_ATTR, streaks)
    threshold = _timeout_threshold()

    def generate_with_timeout_circuit(model_name: str, *args, **kwargs):
        try:
            response = original_generate(model_name, *args, **kwargs)
        except Exception as exc:
            if pipeline_module._is_gemini_transport_timeout(exc):
                streak = int(streaks.get(model_name, 0)) + 1
                streaks[model_name] = streak
                pipeline_module.logger.warning(
                    "[MODEL TIMEOUT STREAK] model=%s streak=%s threshold=%s",
                    model_name, streak, threshold,
                )
                if streak >= threshold:
                    pipeline_module._mark_model_unavailable(
                        model_name,
                        f"transport_timeout_circuit_breaker:{streak}",
                    )
                    pipeline_module.logger.warning(
                        "[MODEL TIMEOUT CIRCUIT OPEN] model=%s threshold=%s; skip for rest of run",
                        model_name, threshold,
                    )
            raise
        else:
            # Consecutive means a successful provider response heals the run-local streak.
            streaks.pop(model_name, None)
            return response

    def rescue_with_vague_quantity_micro_patch(parsed: dict, reason_rows: list[dict]):
        rescued, changes = original_rescue(parsed, reason_rows)
        if changes:
            return rescued, changes

        tokens = _diagnosed_vague_tokens(reason_rows)
        if not tokens:
            return rescued, changes
        protected = _protected_text(parsed)
        if any(token in protected for token in tokens):
            return rescued, changes

        draft = str((parsed or {}).get("note_draft") or "")
        candidate, removed = _remove_vague_quantity_sentences(draft, tokens)
        if not removed or candidate == draft:
            return rescued, changes

        patched = copy.deepcopy(parsed)
        patched["note_draft"] = candidate
        labels = [f"run173_vague_quantity_sentence_removed:{token}" for token in removed]
        pipeline_module.logger.info("[RUN173 MICRO RESCUE] changes=%s", labels)
        return patched, labels

    pipeline_module._generate_via_chat = generate_with_timeout_circuit
    pipeline_module._apply_deterministic_publication_rescue = rescue_with_vague_quantity_micro_patch
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
