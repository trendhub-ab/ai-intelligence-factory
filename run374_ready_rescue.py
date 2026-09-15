"""Run374: convert near-publishable articles into Ready without weakening gates.

This overlay is intentionally narrow. It adds two protections derived from real Run58
failures:
1. a zero-provider, subtractive repair for unsupported vague temporal quantities such as
   ``数日``; and
2. one final Ready Rescue request slot carved out of the existing Deep Dive budget for an
   already-persisted Needs Editorial Review article.

The rescue never raises the per-run Gemini cap, never bypasses Evidence/Fact/Publication/
Reader gates, and never turns Quality Failed or Pending Retry into an eligible model rescue.
"""
from __future__ import annotations

import re
from functools import wraps
from typing import Any

_INSTALL_FLAG = "_run374_ready_rescue_installed"
VAGUE_FAILURE_PREFIX = "unsupported vague quantified claim:"
READER_RESCUE_REQUESTS = 1


def _reason_text(reason_rows: Any) -> str:
    if not reason_rows:
        return ""
    if isinstance(reason_rows, str):
        return reason_rows
    if isinstance(reason_rows, dict):
        return "\n".join(str(value) for value in reason_rows.values())
    if isinstance(reason_rows, (list, tuple, set)):
        return "\n".join(_reason_text(row) for row in reason_rows)
    return str(reason_rows)


def unsupported_vague_tokens(reason_rows: Any) -> list[str]:
    """Return only exact vague-quantity tokens already diagnosed by Fact Gate."""
    text = _reason_text(reason_rows)
    tokens: list[str] = []
    for match in re.finditer(r"unsupported vague quantified claim:\s*([^\s,，。;；\]|}]+)", text):
        token = match.group(1).strip("`'\"()（）[]【】")
        if token and token not in tokens:
            tokens.append(token)
    return tokens[:4]


def _strip_vague_phrase_from_line(line: str, token: str) -> tuple[str, bool]:
    """Delete only the diagnosed temporal modifier; never invent a replacement value."""
    if token not in line:
        return line, False
    stripped = line.lstrip()
    if stripped.startswith("#") or stripped.startswith("http://") or stripped.startswith("https://"):
        return line, False
    if "http://" in line or "https://" in line:
        return line, False

    # Prefer removing the whole adverbial phrase so particles are not stranded.
    suffixes = (
        "以内には", "以内に", "以内で", "以内", "ほどで", "程度で", "程度に",
        "後には", "後に", "後で", "で", "には", "に", "ほど", "程度",
    )
    out = line
    changed = False
    for suffix in suffixes:
        needle = token + suffix
        if needle in out:
            out = out.replace(needle, "", 1)
            changed = True
            break
    if not changed:
        # A bare token is safe to subtract only when punctuation/whitespace bounds it.
        pattern = re.compile(rf"(?<![一-龥ぁ-んァ-ヶA-Za-z0-9]){re.escape(token)}(?![一-龥ぁ-んァ-ヶA-Za-z0-9])")
        out, count = pattern.subn("", out, count=1)
        changed = bool(count)
    if changed:
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = out.replace("、、", "、").replace("。。", "。").replace("、。", "。")
    return out, changed


def remove_unsupported_vague_quantities(article: str, reason_rows: Any) -> tuple[str, list[str]]:
    """Subtractive, code/source-safe repair for exact Fact Gate vague-quantity failures."""
    tokens = unsupported_vague_tokens(reason_rows)
    if not tokens or not article:
        return article or "", []
    lines = str(article).splitlines()
    in_fence = False
    changes: list[str] = []
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        current = line
        for token in tokens:
            current, changed = _strip_vague_phrase_from_line(current, token)
            if changed:
                changes.append(f"remove_unsupported_vague_quantity:{token}")
        lines[index] = current
    repaired = "\n".join(lines)
    # Fail closed: do not report a rescue if the diagnosed token still survives in prose.
    for token in tokens:
        prose = "\n".join(
            line for line in repaired.splitlines()
            if not line.lstrip().startswith("#") and "http://" not in line and "https://" not in line
        )
        if token in prose:
            return article, []
    return repaired, list(dict.fromkeys(changes))


def _install_deterministic_vague_rescue(pipeline: Any) -> None:
    original = getattr(pipeline, "_apply_deterministic_publication_rescue", None)
    if not callable(original) or getattr(pipeline, "_run374_vague_rescue_installed", False):
        return

    @wraps(original)
    def wrapped(parsed: dict, reason_rows):
        rescued, changes = original(parsed, reason_rows)
        out = dict(rescued or {})
        article = str(out.get("note_draft") or "")
        repaired, vague_changes = remove_unsupported_vague_quantities(article, reason_rows)
        if vague_changes:
            out["note_draft"] = repaired
            changes = list(changes or []) + vague_changes
        return out, list(dict.fromkeys(changes or []))

    pipeline._apply_deterministic_publication_rescue = wrapped
    pipeline._run374_vague_rescue_installed = True


def run_reserved_ready_rescue(pipeline: Any, generated_count: int, next_candidate_rank: int) -> tuple[int, int]:
    """Spend at most one *existing* request on a Needs Editorial Review candidate."""
    target = int(getattr(pipeline, "TOP_N_FOR_DEEP_DIVE", 0) or 0)
    if generated_count >= target:
        return generated_count, next_candidate_rank
    budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    original_cap = int(getattr(pipeline, "_run346_original_deep_dive_budget", 0) or 0)
    if budget is None or original_cap <= 0:
        return generated_count, next_candidate_rank
    used = max(0, int(getattr(budget, "used", 0) or 0))
    if used >= original_cap:
        return generated_count, next_candidate_rank

    from article_revalidation import run_existing_editorial_recovery

    previous_cap = int(getattr(budget, "budget", original_cap) or original_cap)
    # One request only. A provider failure cannot cascade across several models here.
    budget.budget = min(original_cap, used + READER_RESCUE_REQUESTS)
    pipeline._READY_RESCUE_ACTIVE = True
    logger = getattr(pipeline, "logger", None)
    if logger:
        logger.info(
            "[RUN374 READY RESCUE SLOT] used=%s rescue_cap=%s total_cap=%s (no quota increase)",
            used, budget.budget, original_cap,
        )
    try:
        return run_existing_editorial_recovery(
            pipeline, generated_count, next_candidate_rank, limit=1
        )
    finally:
        pipeline._READY_RESCUE_ACTIVE = False
        budget.budget = max(previous_cap, original_cap)


def install(pipeline: Any) -> Any:
    """Install deterministic rescue and final orchestration slot idempotently."""
    if getattr(pipeline, _INSTALL_FLAG, False):
        return pipeline
    _install_deterministic_vague_rescue(pipeline)

    original_backlog = getattr(pipeline, "process_article_backlog", None)
    if not callable(original_backlog):
        if getattr(pipeline, "__file__", None):
            raise RuntimeError("Run374 requires pipeline.process_article_backlog")
        return pipeline

    @wraps(original_backlog)
    def backlog_with_ready_rescue(pending_items, generated_count, next_candidate_rank):
        generated_count, next_candidate_rank = original_backlog(
            pending_items, generated_count, next_candidate_rank
        )
        return run_reserved_ready_rescue(pipeline, generated_count, next_candidate_rank)

    pipeline.process_article_backlog = backlog_with_ready_rescue
    setattr(pipeline, _INSTALL_FLAG, True)
    return pipeline
