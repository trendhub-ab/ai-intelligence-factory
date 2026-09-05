"""Pure evidence-context shaping helpers for the AI Intelligence Factory.

This module is deliberately provider-, persistence-, and environment-free.  It owns
only deterministic text-budget operations.  ``pipeline.py`` keeps the thin wrappers
that bind the current runtime limits so tests and operators can still override those
limits dynamically without changing the historical helper signatures.
"""

from __future__ import annotations

import re


def truncate_text_context(text: str, max_chars: int) -> str:
    """Normalize excessive blank lines and apply a deterministic character ceiling."""
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    return text[:max(0, int(max_chars or 0))]


def verification_excerpt(text: str, max_chars: int) -> str:
    """Keep both the beginning and end of long primary-source verification text."""
    normalized = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    limit = max(0, int(max_chars or 0))
    if len(normalized) <= limit:
        return normalized
    if limit <= 64:
        return normalized[:limit]
    marker = "\n\n[...verification context omitted...]\n\n"
    payload = max(0, limit - len(marker))
    head = int(payload * 0.68)
    tail = payload - head
    return normalized[:head] + marker + normalized[-tail:]


def merge_verification_context(existing: str, new_evidence: str, max_chars: int) -> str:
    """Merge existing and newly fetched evidence without dropping the later evidence.

    The newer evidence receives up to 60% of the bounded context.  If either side is
    shorter than its allocation, the unused space is returned to the other side.
    """
    old = re.sub(r"\n{3,}", "\n\n", (existing or "").strip())
    new = re.sub(r"\n{3,}", "\n\n", (new_evidence or "").strip())
    limit = max(0, int(max_chars or 0))
    if not old:
        return verification_excerpt(new, limit)
    if not new:
        return verification_excerpt(old, limit)
    separator = "\n\n"
    if len(old) + len(separator) + len(new) <= limit:
        return old + separator + new
    payload = max(0, limit - len(separator))
    new_budget = min(len(new), int(payload * 0.60))
    old_budget = payload - new_budget
    if len(old) < old_budget:
        extra = old_budget - len(old)
        old_budget = len(old)
        new_budget = min(len(new), new_budget + extra)
    return verification_excerpt(old, old_budget) + separator + verification_excerpt(new, new_budget)
