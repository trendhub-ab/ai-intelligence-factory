"""Run374: convert near-publishable articles into Ready without weakening gates.

This overlay is intentionally narrow. It adds protections derived from real production
failures:
1. zero-provider, subtractive repair for unsupported vague temporal quantities such as
   ``数日``;
2. deterministic rescue loss accounting that lets one or two unsupported sentences be
   removed and then judged by the normal Fact/Publication revalidation path; and
3. one Ready Rescue request slot carved out of the existing Deep Dive budget and offered
   before fresh generation, with a final fallback opportunity only when that slot was not
   consumed.

The rescue never raises the per-run Gemini cap, never bypasses Evidence/Fact/Publication/
Reader gates, and never turns Quality Failed or Pending Retry into an eligible model rescue.
"""
from __future__ import annotations

import re
from functools import wraps
from typing import Any

_INSTALL_FLAG = "_run374_ready_rescue_installed"
_MAIN_PREFLIGHT_FLAG = "_run374_ready_rescue_preflight_installed"
_SLOT_CONSUMED_ATTR = "_run374_ready_rescue_slot_consumed"
_PREFLIGHT_GENERATED_ATTR = "_run374_ready_rescue_preflight_generated"
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


def _normalize_rescue_loss(rescued: dict) -> dict:
    """Count removed sentences, then let canonical gates decide whether the result is safe.

    Run63 exposed a double penalty: two unsupported numeric sentences were correctly
    subtracted, but their numeric nature alone forced an LLM retry before the repaired
    article could be judged by the normal Fact/Publication gates. One or two removals are
    small enough to revalidate deterministically; three or more remain fail-closed.
    """
    out = dict(rescued or {})
    loss = out.get("_rescue_loss")
    if not isinstance(loss, dict):
        return out
    normalized = dict(loss)
    try:
        removed = max(0, int(normalized.get("removed_sentences", 0) or 0))
    except (TypeError, ValueError):
        removed = 3
    normalized["loss_exceeded"] = bool(removed >= 3)
    out["_rescue_loss"] = normalized
    return out


def _install_deterministic_vague_rescue(pipeline: Any) -> None:
    original = getattr(pipeline, "_apply_deterministic_publication_rescue", None)
    if not callable(original) or getattr(pipeline, "_run374_vague_rescue_installed", False):
        return

    @wraps(original)
    def wrapped(parsed: dict, reason_rows):
        rescued, changes = original(parsed, reason_rows)
        out = _normalize_rescue_loss(dict(rescued or {}))
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
    if bool(getattr(pipeline, _SLOT_CONSUMED_ATTR, False)):
        return generated_count, next_candidate_rank
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

    previous_cap = int(getattr(budget, "budget", original_cap) or 0)
    # One request only. A provider failure cannot cascade across several models here.
    budget.budget = min(original_cap, used + READER_RESCUE_REQUESTS)
    pipeline._READY_RESCUE_ACTIVE = True
    pipeline._READY_RESCUE_PROVIDER_SENDS = 0
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
        used_after = max(0, int(getattr(budget, "used", used) or 0))
        if used_after > used:
            setattr(pipeline, _SLOT_CONSUMED_ATTR, True)
        pipeline._READY_RESCUE_ACTIVE = False
        # Restore the caller's partition. Preflight callers need the Fresh cap back;
        # the historical post-backlog caller already arrives with the full cap.
        budget.budget = previous_cap


def _install_ready_rescue_preflight(pipeline: Any) -> None:
    """Offer rescue after run initialization and before fresh provider calls.

    If that single request is consumed, shift the Fresh cumulative cap by the same one
    request so Fresh still owns eight requests. Return its Ready count and candidate
    rank to the normal loop, preserving the total target, audit artifacts and funnel.
    Wrapping main before its resets erased the rescue's audit and delivery accounting.
    """
    if getattr(pipeline, _MAIN_PREFLIGHT_FLAG, False):
        return

    def ready_rescue_preflight() -> tuple[int, int]:
        reserved = max(0, int(getattr(pipeline, "_run374_ready_rescue_reserved_requests", 0) or 0))
        budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
        original_cap = max(0, int(getattr(pipeline, "_run346_original_deep_dive_budget", 0) or 0))
        original_target = max(0, int(getattr(pipeline, "TOP_N_FOR_DEEP_DIVE", 0) or 0))
        if reserved <= 0 or budget is None or original_cap <= 0 or original_target <= 0:
            return 0, 0

        fresh_cap = max(0, int(getattr(budget, "budget", 0) or 0))
        used_before = max(0, int(getattr(budget, "used", 0) or 0))
        pre_generated, next_rank = run_reserved_ready_rescue(pipeline, 0, 0)
        used_after = max(0, int(getattr(budget, "used", used_before) or 0))
        consumed = max(0, used_after - used_before)
        pre_generated = max(0, min(original_target, int(pre_generated or 0)))
        setattr(pipeline, _PREFLIGHT_GENERATED_ATTR, pre_generated)

        if consumed:
            # The rescue request came out of the same total-12 envelope. Raising the
            # cumulative Fresh cap from 8 to 9 restores eight *additional* Fresh requests.
            budget.budget = min(original_cap, fresh_cap + consumed)

        logger = getattr(pipeline, "logger", None)
        if logger:
            logger.info(
                "[RUN374 READY RESCUE PREFLIGHT] consumed=%s generated=%s fresh_cap=%s downstream_cap=%s target=%s",
                consumed, pre_generated, fresh_cap, getattr(budget, "budget", 0), original_target,
            )

        return pre_generated, next_rank

    pipeline._run374_ready_rescue_preflight = ready_rescue_preflight
    setattr(pipeline, _MAIN_PREFLIGHT_FLAG, True)


def install(pipeline: Any) -> Any:
    """Install deterministic rescue plus preflight/final orchestration idempotently."""
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
        # If preflight already spent the reserved request, this is a no-op. Otherwise it
        # remains the historical final chance for runs with no eligible preflight candidate.
        return run_reserved_ready_rescue(pipeline, generated_count, next_candidate_rank)

    pipeline.process_article_backlog = backlog_with_ready_rescue
    _install_ready_rescue_preflight(pipeline)
    setattr(pipeline, _INSTALL_FLAG, True)
    return pipeline
